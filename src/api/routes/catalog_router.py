import re
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, defer

from src.api.schemas.catalog import (
    CatalogListResponse,
    CatalogModItem,
    CatalogSyncRequest,
    CatalogSyncStatusResponse,
    ModDetailsResponse,
)
from src.infrastructure.database.models import CatalogMod, InstalledMod
from src.api.deps import get_db
from src.providers import ProviderRegistry
from src.application.catalog.catalog_sync_service import (
    SyncTracker,
    run_catalog_sync,
)
from src.application.dependencies.dependency_resolver import resolve_mod_dependencies
from src.application.mods.mod_installer_service import perform_mod_install
from src.application.mods.mod_update_service import check_has_update
from src.utils.logger import logger


from src.api.routes.catalog_reports_router import reports_router
from src.api.routes.catalog_install_router import install_router
from src.infrastructure.database.catalog_queries import build_catalog_query

_run_catalog_sync = run_catalog_sync
_perform_install = perform_mod_install

router = APIRouter(prefix="/catalog", tags=["Catalog"])
router.include_router(reports_router)
router.include_router(install_router)


@router.get("", response_model=CatalogListResponse)
def get_catalog(
    search: Optional[str] = None,
    source: Optional[str] = Query(None, description="loverslab, nsfwmods, curseforge, thesimsresource, patreon, all"),
    access: Optional[str] = Query(None, description="public, unlocked, locked, all"),
    status: Optional[str] = Query(None, description="all, installed, not_installed, updates_available"),
    mod_type: Optional[str] = Query(None, description="animation, clothing, hair, body_skin, etc."),
    sort: Optional[str] = Query("recent", description="recent, az"),
    include_adult: Optional[bool] = Query(None, description="Include adult (+18) sources (LoversLab, NSFWMods)"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
):
    """Returns catalog mods with filtering, search, status, and pagination using SQL-level filtering."""
    from src.core.config import AppConfig

    effective_adult = include_adult if include_adult is not None else AppConfig.load().adult_content_enabled
    from src.infrastructure.cache.catalog_cache import CatalogQueryCache

    cache_key = CatalogQueryCache.make_key(
        search=search or "",
        source=source or "",
        access=access or "",
        status=status or "",
        mod_type=mod_type or "",
        sort=sort or "",
        include_adult=effective_adult,
        page=page,
        limit=limit,
    )
    cached_res = CatalogQueryCache.get_instance().get(cache_key)
    if cached_res is not None:
        return cached_res

    query = build_catalog_query(
        session=session,
        search=search,
        source=source,
        access=access,
        status=status,
        mod_type=mod_type,
        sort=sort,
        include_adult=effective_adult,
    )

    total = int(query.order_by(None).with_entities(func.count(CatalogMod.id)).scalar() or 0)
    paginated_mods = query.options(defer(CatalogMod.description)).offset((page - 1) * limit).limit(limit).all()

    # Load all installed mods once (small table) so both parent status AND dependency status resolve accurately
    all_installed = session.query(InstalledMod).options(defer(InstalledMod.installed_files)).all()
    installed_by_remote = {
        ((im.source or "unknown").lower(), str(im.remote_id)): im for im in all_installed if im.remote_id
    }
    installed_by_title = {im.title.strip().lower(): im for im in all_installed if im.title}
    installed_by_fp = {im.title_fingerprint: im for im in all_installed if getattr(im, "title_fingerprint", None)}
    installed_by_id = {im.catalog_mod_id: im for im in all_installed if im.catalog_mod_id and not im.remote_id}

    # Pre-collect all requirement remote_ids for batch lookup (eliminates N+1 queries)
    needed_remote_ids = set()
    for m in paginated_mods:
        for req in m.get_requirements_mods_list():
            rid = str(req.get("remote_id") or "")
            if rid:
                needed_remote_ids.add(rid)

    catalog_remote_ids = set()
    if needed_remote_ids:
        found_rows = (
            session.query(CatalogMod.source, CatalogMod.remote_id)
            .filter(CatalogMod.remote_id.in_(list(needed_remote_ids)))
            .all()
        )
        catalog_remote_ids = {(row[0], str(row[1])) for row in found_rows}

    paginated_items = []
    for m in paginated_mods:
        m_source = (m.source or "unknown").lower()
        m_rid = str(m.remote_id or "")
        m_title = (m.title or "").strip().lower()

        m_fp = getattr(m, "title_fingerprint", "") or ""
        inst = (
            installed_by_remote.get((m_source, m_rid))
            or installed_by_id.get(m.id)
            or (installed_by_title.get(m_title) if m_title else None)
            or (installed_by_fp.get(m_fp) if m_fp else None)
        )
        is_installed = inst is not None
        has_update = check_has_update(inst, m) if inst is not None else False

        dep_items = resolve_mod_dependencies(
            m.get_requirements_mods_list(),
            session,
            installed_by_remote,
            installed_by_title,
            is_syncing=SyncTracker.is_running,
            catalog_remote_ids=catalog_remote_ids,
            requirements_overrides=m.get_requirements_overrides(),
        )

        paginated_items.append(
            CatalogModItem(
                id=m.id,
                source=m.source,
                remote_id=m.remote_id,
                title=m.title,
                author=m.author or "",
                category=m.category or "",
                page_url=m.page_url,
                thumbnail_url=m.thumbnail_url or "",
                published_date=m.published_date,
                updated_date=m.updated_date,
                patreon_status=m.patreon_status or "NONE",
                patreon_tier=m.patreon_tier or "",
                tags=m.get_tags_list(),
                is_installed=is_installed,
                has_update=has_update,
                requirements_text=m.requirements_text,
                requirements_status=m.requirements_status or "NONE",
                dependencies=dep_items,
            )
        )

    result = CatalogListResponse(
        total=total,
        page=page,
        limit=limit,
        items=paginated_items,
    )
    CatalogQueryCache.get_instance().set(cache_key, result)
    return result


@router.post("/sync", response_model=CatalogSyncStatusResponse)
def start_sync(payload: CatalogSyncRequest, background_tasks: BackgroundTasks):
    """Triggers multi-source catalog synchronization."""
    from src.core.config import AppConfig, ADULT_PROVIDERS

    if SyncTracker.is_running:
        resp = SyncTracker.to_response()
        resp.message = "Une synchronisation est déjà en cours d'exécution."
        return resp

    adult_enabled = AppConfig.load().adult_content_enabled
    providers = ProviderRegistry.list_providers()
    categories: list[dict[str, Any]] = []
    active_provider_names: list[str] = []
    for p in providers:
        p_name = getattr(p, "provider_name", "").lower()
        if not adult_enabled and p_name in ADULT_PROVIDERS:
            continue
        p_cats = getattr(p, "CATEGORIES", [])
        if p_cats:
            categories.extend(p_cats)
            if p_name:
                active_provider_names.append(p_name)
    initial_pages = (
        sum(c.get("default_pages", 1) for c in categories)
        if payload.max_pages <= 0
        else sum(min(payload.max_pages, c.get("default_pages", 1)) for c in categories)
    )
    page_msg = "toutes les pages détectées" if payload.max_pages <= 0 else f"{payload.max_pages} pages par source"
    SyncTracker.start(
        initial_pages,
        categories_list=categories,
        max_pages_per_cat=payload.max_pages,
        active_providers=active_provider_names,
    )
    SyncTracker.message = f"Synchronisation démarrée ({page_msg})."
    if payload.is_background:
        background_tasks.add_task(_run_catalog_sync, payload.max_pages, payload.is_background)
    else:
        background_tasks.add_task(_run_catalog_sync, payload.max_pages)
    return SyncTracker.to_response()


@router.get("/sync/status", response_model=CatalogSyncStatusResponse)
def get_sync_status():
    """Returns current catalog scraping progress status."""
    return SyncTracker.to_response()


@router.post("/sync/pause", response_model=CatalogSyncStatusResponse)
def pause_sync(provider: Optional[str] = Query(None, description="Nom du provider (ex: loverslab)")):
    """Pauses the current catalog synchronization."""
    SyncTracker.pause(provider=provider)
    return SyncTracker.to_response()


@router.post("/sync/resume", response_model=CatalogSyncStatusResponse)
def resume_sync(provider: Optional[str] = Query(None, description="Nom du provider (ex: loverslab)")):
    """Resumes the paused catalog synchronization."""
    SyncTracker.resume(provider=provider)
    return SyncTracker.to_response()


@router.post("/sync/stop", response_model=CatalogSyncStatusResponse)
def stop_sync(provider: Optional[str] = Query(None, description="Nom du provider (ex: loverslab)")):
    """Stops the current catalog synchronization."""
    SyncTracker.stop(provider=provider)
    return SyncTracker.to_response()


@router.get("/{mod_id:int}/details", response_model=ModDetailsResponse)
@router.get("/{mod_id:int}", response_model=ModDetailsResponse)
def get_catalog_mod_details(mod_id: int, force_refresh: bool = False, session: Session = Depends(get_db)):
    """Returns full details for a catalog mod by ID."""
    m = session.query(CatalogMod).filter_by(id=mod_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mod introuvable dans le catalogue.")

    desc = m.description
    is_legacy = (
        desc
        and desc.strip()
        and (
            len(desc.strip()) < 50
            or "<div" not in desc
            or "background-color:#0d0d0d" in desc
            or "background-color:" in desc
        )
    )
    needs_remote_fetch = (
        force_refresh
        or not desc
        or is_legacy
        or m.requirements_status is None
        or (m.requirements_text and not m.get_requirements_mods_list() and m.requirements_status != "RESOLVED")
    )
    details_dict: dict[str, Any] = {}
    if needs_remote_fetch and m.page_url:
        try:
            provider = ProviderRegistry.get_provider(str(m.source or "loverslab"))
            if provider:
                details = provider.get_mod_details(m.page_url)
                details_dict = (
                    details.model_dump()
                    if hasattr(details, "model_dump")
                    else (details if isinstance(details, dict) else {})
                )
                fetched_desc = details_dict.get("description", "")
                if fetched_desc:
                    m.description = fetched_desc
                    desc = fetched_desc
                if details_dict.get("requirements_text") is not None or details_dict.get("requirements_status"):
                    m.requirements_text = details_dict.get("requirements_text")
                    m.requirements_status = details_dict.get("requirements_status", "NONE")
                    m.set_requirements_mods_list(details_dict.get("requirements_mods", []))
                if details_dict.get("download_urls"):
                    m.set_download_urls_list(details_dict.get("download_urls", []))
                if details_dict.get("external_links"):
                    m.set_external_links_list(details_dict.get("external_links", []))
                session.commit()
        except Exception as e:
            logger.debug(f"Erreur extraction détails/requirements pour {m.title}: {e}")

    all_inst = session.query(InstalledMod).options(defer(InstalledMod.installed_files)).all()
    installed_by_remote = {(im.source or "unknown", im.remote_id): im for im in all_inst if im.remote_id}
    installed_by_title = {im.title.lower(): im for im in all_inst if im.title}
    dep_items = resolve_mod_dependencies(
        m.get_requirements_mods_list(),
        session,
        installed_by_remote,
        installed_by_title,
        is_syncing=SyncTracker.is_running,
        requirements_overrides=m.get_requirements_overrides(),
    )

    screenshots = details_dict.get("screenshots", [])
    if not screenshots and desc:
        imgs_in_desc = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', str(desc or ""))
        screenshots = [
            u
            for u in imgs_in_desc
            if any(k in u.lower() for k in ["screenshot", "upload", "gallery", "image"])
            and not any(k in u.lower() for k in ["reaction", "icon", "theme", "emoticon"])
        ]

    return ModDetailsResponse(
        id=m.id,
        source=str(m.source or "unknown"),
        remote_id=str(m.remote_id or ""),
        title=str(m.title or "Untitled"),
        author=m.author or "Inconnu",
        description=desc or "Aucune description détaillée disponible pour ce mod.",
        page_url=str(m.page_url or ""),
        thumbnail_url=m.thumbnail_url or "",
        tags=m.get_tags_list(),
        updated_date=m.updated_date.strftime("%d/%m/%Y") if m.updated_date else None,
        patreon_status=m.patreon_status or "NONE",
        patreon_tier=m.patreon_tier or "",
        requirements_text=m.requirements_text,
        requirements_status=m.requirements_status or "NONE",
        dependencies=dep_items,
        screenshots=screenshots,
        download_urls=m.get_download_urls_list(),
        external_links=m.get_external_links_list(),
    )
