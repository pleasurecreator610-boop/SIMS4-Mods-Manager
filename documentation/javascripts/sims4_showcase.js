/**
 * Filtrage interactif temps réel des 22 plateformes sur la GitHub Page SIMS 4 Mods Manager.
 */
document.addEventListener("DOMContentLoaded", () => {
  const buttons = document.querySelectorAll(".s4-filter-btn");
  const searchInput = document.getElementById("s4-provider-search");
  const cards = document.querySelectorAll(".s4-provider-card");

  if (!cards.length) return;

  let activeCategory = "all";

  function applyFilters() {
    const query = (searchInput ? searchInput.value : "").trim().toLowerCase();
    cards.forEach((card) => {
      const cat = card.getAttribute("data-category") || "";
      const tags = card.getAttribute("data-tags") || "";
      const text = card.textContent.toLowerCase();

      const matchesCategory =
        activeCategory === "all" ||
        cat === activeCategory ||
        tags.split(",").includes(activeCategory);
      const matchesSearch = !query || text.includes(query);

      card.style.display = matchesCategory && matchesSearch ? "flex" : "none";
    });
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeCategory = btn.getAttribute("data-filter") || "all";
      applyFilters();
    });
  });

  if (searchInput) {
    searchInput.addEventListener("input", applyFilters);
  }
});
