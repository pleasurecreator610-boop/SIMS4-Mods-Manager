"""
Unit & Integration tests for:
1. Official Framework Redirection (Deaderpool, Scumbumbo, Lumpinou, WickedWhims/wickedcc, Basemental, Sims 4 Studio).
2. Multi-mod installation with multiple dependencies from the same platform and across platforms.
3. ActiveInstallationRegistry concurrent deduplication of shared dependencies across threads.
4. Cross-platform installation of the same mod across different platforms without collision or duplicate download.
"""

import threading

from src.application.dependencies.dependency_resolver import (
    find_special_dependency_case,
    resolve_mod_dependencies,
)
from src.application.mods.active_installation_registry import ActiveInstallationRegistry
from src.infrastructure.database import CatalogMod, DatabaseManager, InstalledMod
from src.utils.mod_matcher import ModMatcher


def test_official_framework_redirection_over_third_party_urls():
    """
    Verifies that dependencies on Deaderpool (MCCC), Scumbumbo (XML Injector),
    Lumpinou (RPO, Mood Pack, Toolbox), WickedWhims (wickedcc), and Basemental
    ALWAYS resolve to their official websites even when the mod's requirement link
    points to LoversLab (#3169), CurseForge, or ModTheSims.
    """
    # 1. WickedWhims pointing to LoversLab #3169 must redirect to official wicked.cc
    ww = find_special_dependency_case(
        "WickedWhims",
        url="https://www.loverslab.com/files/file/3169-wickedwhims/",
        remote_id="3169",
    )
    assert ww is not None
    assert ww["source"] == "wickedcc"
    assert ww["url"] == "https://wicked.cc/download/3169-wickedwhims/"

    # 2. MCCC / MC Command Center pointing to CurseForge must redirect to deaderpool-mccc.com
    mccc = find_special_dependency_case(
        "MC Command Center",
        url="https://www.curseforge.com/sims4/mods/mc-command-center",
        remote_id="cf-mccc",
    )
    assert mccc is not None
    assert mccc["source"] == "deaderpool"
    assert "deaderpool-mccc.com" in mccc["url"]

    # 3. Scumbumbo XML Injector pointing to ModTheSims/CurseForge must redirect to scumbumbomods.com
    xml_inj = find_special_dependency_case(
        "Scumbumbo's XML Injector v4",
        url="https://modthesims.info/d/622928/xml-injector.html",
    )
    assert xml_inj is not None
    assert xml_inj["source"] == "scumbumbo"
    assert xml_inj["url"] == "https://scumbumbomods.com/xml-injector"

    # 4. Lumpinou RPO / Mood Pack / Toolbox must redirect to lumpinoumods.com
    rpo = find_special_dependency_case("Relationship & Pregnancy Overhaul (RPO)")
    assert rpo is not None
    assert rpo["source"] == "lumpinou"
    assert "lumpinoumods.com" in rpo["url"]

    mood_pack = find_special_dependency_case("Lumpinou's Mood Pack Mod")
    assert mood_pack is not None
    assert mood_pack["source"] == "lumpinou"
    assert "lumpinoumods.com/mood-pack-mod" in mood_pack["url"]

    toolbox = find_special_dependency_case("Lumpinou's Toolbox")
    assert toolbox is not None
    assert toolbox["source"] == "lumpinou"
    assert "lumpinoumods.com/lumpinous-toolbox" in toolbox["url"]

    # 5. Basemental Drugs & Universal Venue List must redirect to basementalcc.com
    b_drugs = find_special_dependency_case("Basemental Drugs")
    assert b_drugs is not None
    assert b_drugs["source"] == "basemental"
    assert b_drugs["url"] == "https://basementalcc.com/adult_mods/basemental-drugs/"

    uvl = find_special_dependency_case("Basemental Universal Venue List")
    assert uvl is not None
    assert uvl["source"] == "basemental"
    assert uvl["url"] == "https://basementalcc.com/mods/universal-venue-list/"


def test_multi_mod_installation_with_same_platform_and_cross_platform_dependencies():
    """
    Simulates installing multiple mods simultaneously where:
    - Mod A (from synthira) requires 2 same-platform dependencies (synthira) + 2 cross-platform official frameworks (WickedWhims + XML Injector).
    - Mod B (from gamebanana) requires 1 same-platform dependency (gamebanana) + XML Injector + Lumpinou Mood Pack.
    Verifies resolution, official redirection, and ActiveInstallationRegistry concurrency deduplication across threads.
    """
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        session.query(CatalogMod).delete()
        session.query(InstalledMod).delete()

        # Register same-platform catalog mods for Synthira and GameBanana
        session.add_all(
            [
                CatalogMod(
                    source="synthira",
                    remote_id="syn-core-mesh",
                    title="Synthira Core High Poly Mesh",
                    author="SynthiraArtist",
                    page_url="https://synthira.ru/load/12-1-0-501",
                ),
                CatalogMod(
                    source="synthira",
                    remote_id="syn-rig-pack",
                    title="Synthira Animation Rig Pack",
                    author="SynthiraArtist",
                    page_url="https://synthira.ru/load/12-1-0-502",
                ),
                CatalogMod(
                    source="gamebanana",
                    remote_id="gb-shader-core",
                    title="GameBanana Shader Core Library",
                    author="GBCreator",
                    page_url="https://gamebanana.com/mods/9001",
                ),
            ]
        )
        session.commit()

        raw_deps_a = [
            {
                "source": "synthira",
                "remote_id": "syn-core-mesh",
                "title": "Synthira Core High Poly Mesh",
                "url": "https://synthira.ru/load/12-1-0-501",
            },
            {
                "source": "synthira",
                "remote_id": "syn-rig-pack",
                "title": "Synthira Animation Rig Pack",
                "url": "https://synthira.ru/load/12-1-0-502",
            },
            {
                "source": "loverslab",
                "remote_id": "3169",
                "title": "WickedWhims",
                "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
            },
            {
                "source": "curseforge",
                "remote_id": "cf-xml",
                "title": "XML Injector",
                "url": "https://www.curseforge.com/sims4/mods/xml-injector",
            },
        ]

        raw_deps_b = [
            {
                "source": "gamebanana",
                "remote_id": "gb-shader-core",
                "title": "GameBanana Shader Core Library",
                "url": "https://gamebanana.com/mods/9001",
            },
            {
                "source": "modthesims",
                "remote_id": "mts-xml",
                "title": "Scumbumbo XML Injector",
                "url": "https://modthesims.info/d/622928/xml-injector.html",
            },
            {
                "source": "patreon",
                "remote_id": "pat-mood",
                "title": "Mood Pack Mod",
                "url": "https://www.patreon.com/posts/mood-pack-mod",
            },
        ]

        resolved_a = resolve_mod_dependencies(
            raw_deps_a,
            session,
            installed_by_remote={},
            installed_by_title={},
            is_syncing=False,
        )
        resolved_b = resolve_mod_dependencies(
            raw_deps_b,
            session,
            installed_by_remote={},
            installed_by_title={},
            is_syncing=False,
        )

        deps_a = {d.title: d for d in resolved_a}
        deps_b = {d.title: d for d in resolved_b}

        # Verify Mod A same-platform + official redirected dependencies
        assert deps_a["Synthira Core High Poly Mesh"].source == "synthira"
        assert deps_a["Synthira Core High Poly Mesh"].status == "DETECTED_NOT_INSTALLED"
        assert deps_a["Synthira Animation Rig Pack"].source == "synthira"
        assert deps_a["WickedWhims"].source == "wickedcc"
        assert deps_a["WickedWhims"].url == "https://wicked.cc/download/3169-wickedwhims/"
        assert deps_a["XML Injector"].source == "scumbumbo"
        assert deps_a["XML Injector"].url == "https://scumbumbomods.com/xml-injector"

        # Verify Mod B same-platform + official redirected dependencies
        assert deps_b["GameBanana Shader Core Library"].source == "gamebanana"
        assert deps_b["XML Injector"].source == "scumbumbo"
        assert deps_b["Mood Pack Mod"].source == "lumpinou"
        assert "lumpinoumods.com/mood-pack-mod" in deps_b["Mood Pack Mod"].url

    # Verify ActiveInstallationRegistry deduplicates XML Injector across two concurrent worker threads
    ActiveInstallationRegistry.reset()
    reg = ActiveInstallationRegistry.get_instance()
    acquired_main, _ev_main = reg.register_install("scumbumbo", "scumbumbo_xml_injector", "XML Injector")
    assert acquired_main is True

    other_thread_result = []

    def _second_installer_worker():
        ok, _ev = reg.register_install("scumbumbo", "scumbumbo_xml_injector", "XML Injector")
        other_thread_result.append(ok)

    t = threading.Thread(target=_second_installer_worker)
    t.start()
    t.join(timeout=5.0)
    assert other_thread_result == [False]

    reg.complete_install("scumbumbo", "scumbumbo_xml_injector", "XML Injector", success=True)
    ActiveInstallationRegistry.reset()


def test_same_mod_installed_across_multiple_platforms_detected_and_deduplicated():
    """
    Tests when the exact same mod is listed on multiple platforms
    (e.g. installed from 'scumbumbo', 'wickedcc', or 'littlemssam', and required or browsed from
    'curseforge', 'modthesims', 'thesimscatalog', or 'loverslab'):
    - ModMatcher.canonical_fingerprint matches the mod regardless of platform or version suffix.
    - resolve_mod_dependencies marks the dependency as INSTALLED without re-downloading.
    """
    # 1. Canonical fingerprint identity across platforms and version strings (via clean_mod_title)
    fp_official = ModMatcher.canonical_fingerprint(ModMatcher.clean_mod_title("MC Command Center v2026.2.0"))
    fp_curseforge = ModMatcher.canonical_fingerprint(ModMatcher.clean_mod_title("Sims 4 MC Command Center v2026.1.0"))
    assert fp_official == fp_curseforge

    fp_lms_official = ModMatcher.canonical_fingerprint(ModMatcher.clean_mod_title("More Buyable Venues v1.4 [TS4]"))
    fp_lms_cf = ModMatcher.canonical_fingerprint(ModMatcher.clean_mod_title("Sims 4 More Buyable Venues"))
    assert fp_lms_official == fp_lms_cf

    # 2. Install XML Injector from official 'scumbumbo' provider, WickedWhims from 'wickedcc',
    # and More Buyable Venues from 'littlemssam'
    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        session.query(InstalledMod).delete()
        mod_xml = InstalledMod(
            title="XML Injector",
            source="scumbumbo",
            remote_id="scumbumbo_xml_injector",
            version_str="4.1",
            folder_name="scumbumbo_XML_Injector_101",
            is_enabled=True,
        )
        mod_ww = InstalledMod(
            title="WickedWhims",
            source="wickedcc",
            remote_id="3169",
            version_str="v182",
            folder_name="wickedcc_WickedWhims_102",
            is_enabled=True,
        )
        mod_lms = InstalledMod(
            title="More Buyable Venues",
            source="littlemssam",
            remote_id="lms_venues",
            version_str="1.0",
            folder_name="littlemssam_MoreBuyableVenues_103",
            is_enabled=True,
        )
        session.add_all([mod_xml, mod_ww, mod_lms])
        session.commit()

        installed_by_remote = {
            ("scumbumbo", "scumbumbo_xml_injector"): mod_xml,
            ("wickedcc", "3169"): mod_ww,
            ("littlemssam", "lms_venues"): mod_lms,
        }
        installed_by_title = {
            "xml injector": mod_xml,
            "wickedwhims": mod_ww,
            "more buyable venues": mod_lms,
        }

        # Now resolve a mod from F95zone/TheSimsCatalog that asks for WickedWhims (via LoversLab URL),
        # XML Injector (via CurseForge URL), and More Buyable Venues (via TheSimsCatalog URL)
        raw_cross_platform_deps = [
            {
                "source": "loverslab",
                "remote_id": "3169",
                "title": "WickedWhims",
                "url": "https://www.loverslab.com/files/file/3169-wickedwhims/",
            },
            {
                "source": "curseforge",
                "remote_id": "cf-991",
                "title": "XML Injector",
                "url": "https://www.curseforge.com/sims4/mods/xml-injector",
            },
            {
                "source": "thesimscatalog",
                "remote_id": "tsc-882",
                "title": "Sims 4 More Buyable Venues v1.2",
                "url": "https://thesimscatalog.com/sims4/downloads/game-mods/more-buyable-venues/",
            },
        ]

        resolved = resolve_mod_dependencies(
            raw_cross_platform_deps,
            session,
            installed_by_remote=installed_by_remote,
            installed_by_title=installed_by_title,
            is_syncing=False,
        )
        for dep in resolved:
            assert dep.is_installed is True, f"Expected '{dep.title}' to be detected as installed across platforms"
            assert dep.status == "INSTALLED"
