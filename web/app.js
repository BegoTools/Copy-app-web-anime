/**
 * Anime Rift — PlayStation 5 Edition (FW 13.60 Jailbreak)
 * Full DualSense Spatial Navigation, Live API Integration & HLS/MP4 Video Player
 */

(function () {
  "use strict";

  // =========================================================================
  // APPLICATION STATE
  // =========================================================================
  const state = {
    activeTab: "home",
    tabsOrder: ["home", "schedule", "search", "favorites", "history"],
    homeData: null,
    genresList: [],
    banners: [],
    bannerIndex: 0,
    bannerTimer: null,

    scheduleData: null,
    selectedScheduleDay: null,

    searchQuery: "",
    searchSort: "latest_episode_released",
    searchStatus: "",
    searchType: "",
    searchGenreId: "",
    searchPage: 1,
    searchResults: [],

    userData: {
      favorites: [],
      watch_history: [],
      progress: {},
      settings: {
        language: "ar",
        auto_skip_intro: true,
        auto_skip_outro: false,
      },
    },

    // Details Modal State
    detailsOpen: false,
    currentAnime: null,
    currentEpisodes: [],
    epSortAsc: false,
    epRangeIndex: 0,
    epPageSize: 60,

    // Video Player State
    playerOpen: false,
    playingEpisode: null,
    episodeSources: [],
    selectedSourceIndex: 0,
    hlsInstance: null,
    hudTimer: null,
    progressSaveTimer: null,

    // Focus Management
    focusedEl: null,
    lastFocusBeforeDetails: null,
    lastFocusBeforePlayer: null,
  };

  const DAY_AR = {
    saturday: "السبت",
    sunday: "الأحد",
    monday: "الإثنين",
    tuesday: "الثلاثاء",
    wednesday: "الأربعاء",
    thursday: "الخميس",
    friday: "الجمعة",
  };

  // =========================================================================
  // HELPERS & API CLIENT
  // =========================================================================
  const $ = (id) => document.getElementById(id);

  function showToast(msg) {
    const t = $("ps5-toast");
    if (!t) return;
    t.textContent = msg;
    t.classList.remove("hidden");
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.add("hidden"), 3200);
  }

  function setAmbientBackground(imgUrl) {
    const bg = $("ambient-bg");
    if (bg && imgUrl) {
      bg.style.backgroundImage = `url("${imgUrl}")`;
    }
  }

  function formatTime(sec) {
    if (!sec || ! isFinite(sec) || sec < 0) return "00:00";
    const s = Math.floor(sec);
    const hrs = Math.floor(s / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = s % 60;
    if (hrs > 0) {
      return `${hrs}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    }
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }

  async function apiGet(path) {
    try {
      const res = await fetch(path);
      if (res.ok) return await res.json();
    } catch (e) {}
    if (path.startsWith("/api/home")) {
      const fb = await fetch("api_cache/home.json");
      if (fb.ok) return await fb.json();
    } else if (path.startsWith("/api/schedule")) {
      const fb = await fetch("api_cache/schedule.json");
      if (fb.ok) return await fb.json();
    }
    throw new Error(`HTTP error on ${path}`);
  }

  async function apiPost(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }

  // =========================================================================
  // USER DATA PERSISTENCE (LocalStorage + Disk Backup via /api/userdata)
  // =========================================================================
  async function loadUserData() {
    try {
      const localRaw = localStorage.getItem("animerift_ps5_userdata");
      if (localRaw) {
        const parsed = JSON.parse(localRaw);
        Object.assign(state.userData, parsed);
      }
    } catch (e) {}

    try {
      const remote = await apiGet("/api/userdata");
      if (remote && !remote.error) {
        if (remote.favorites?.length || !state.userData.favorites.length) {
          state.userData.favorites = remote.favorites || [];
        }
        if (remote.watch_history?.length || !state.userData.watch_history.length) {
          state.userData.watch_history = remote.watch_history || [];
        }
        state.userData.progress = Object.assign(
          {},
          remote.progress || {},
          state.userData.progress || {}
        );
      }
    } catch (e) {}
  }

  function saveUserData() {
    try {
      localStorage.setItem("animerift_ps5_userdata", JSON.stringify(state.userData));
    } catch (e) {}
    apiPost("/api/userdata", state.userData).catch(() => {});
  }

  function isFavorite(animeId) {
    return state.userData.favorites.some((item) => item._id === animeId);
  }

  function toggleFavorite(animeObj) {
    if (!animeObj || !animeObj._id) return;
    const idx = state.userData.favorites.findIndex((x) => x._id === animeObj._id);
    if (idx >= 0) {
      state.userData.favorites.splice(idx, 1);
      showToast(`تمت إزالة "${animeObj.title}" من قائمتي`);
    } else {
      state.userData.favorites.unshift({
        _id: animeObj._id,
        title: animeObj.title,
        alternative_title: animeObj.alternative_title,
        main_picture: animeObj.main_picture || animeObj.medium_picture || animeObj.banner_picture,
        myAnimeList_rating: animeObj.myAnimeList_rating,
        content_type: animeObj.content_type || "tv",
        release_year: animeObj.release_year,
        latest_episode_released: animeObj.latest_episode_released,
      });
      showToast(`❤️ تمت إضافة "${animeObj.title}" إلى قائمتي`);
    }
    saveUserData();
    updateHeroFavoriteButton();
    updateDetailsFavoriteButton();
    if (state.activeTab === "favorites") renderFavoritesView();
  }

  function recordWatchProgress(anime, ep, currentTime, duration) {
    if (!anime || !ep || !duration || duration < 10) return;
    const key = `${anime._id}_${ep.episode_number}`;
    state.userData.progress[key] = {
      currentTime: Math.floor(currentTime),
      duration: Math.floor(duration),
      episodeId: ep._id,
      episodeNumber: ep.episode_number,
      updatedAt: Date.now(),
    };

    const existingIdx = state.userData.watch_history.findIndex(
      (x) => x._id === anime._id
    );
    const entry = {
      _id: anime._id,
      title: anime.title,
      main_picture: ep.thumbnail || anime.main_picture || anime.medium_picture,
      myAnimeList_rating: anime.myAnimeList_rating,
      content_type: anime.content_type || "tv",
      lastEpisodeNumber: ep.episode_number,
      lastEpisodeId: ep._id,
      currentTime: Math.floor(currentTime),
      duration: Math.floor(duration),
      updatedAt: Date.now(),
    };
    if (existingIdx >= 0) {
      state.userData.watch_history.splice(existingIdx, 1);
    }
    state.userData.watch_history.unshift(entry);
    if (state.userData.watch_history.length > 50) {
      state.userData.watch_history.length = 50;
    }
    saveUserData();
  }

  // =========================================================================
  // CARD BUILDER
  // =========================================================================
  function createAnimeCard(item, isHistoryCard = false) {
    const card = document.createElement("div");
    card.className = "anime-card focusable";
    card.tabIndex = 0;
    card.dataset.animeId = item._id;

    const poster =
      item.main_picture ||
      item.medium_picture ||
      item.large_picture ||
      item.banner_picture ||
      "assets/app_logo.png";

    const rating = item.myAnimeList_rating
      ? `★ ${Number(item.myAnimeList_rating).toFixed(2)}`
      : "★ جديد";

    const epNum = isHistoryCard
      ? item.lastEpisodeNumber
      : item.latest_episode_released?.episode_number || item.available_episodes;

    const epBadgeText = epNum ? `حلقة ${epNum}` : (item.content_type || "TV").toUpperCase();
    const fav = isFavorite(item._id);

    let progressHtml = "";
    if (isHistoryCard && item.duration > 0) {
      const pct = Math.min(100, Math.round((item.currentTime / item.duration) * 100));
      progressHtml = `
        <div class="card-progress-bar">
          <div class="card-progress-fill" style="width:${pct}%"></div>
        </div>
      `;
    }

    const subLeft = isHistoryCard
      ? `${formatTime(item.currentTime)} / ${formatTime(item.duration)}`
      : item.release_year || item.release_status || "";

    card.innerHTML = `
      <div class="card-poster-wrap">
        <img class="card-poster" src="${poster}" alt="${item.title || ""}" loading="lazy" onerror="this.src='assets/app_logo.png'" />
        <div class="card-top-badges">
          <span class="card-rating">${rating}</span>
          <span class="card-ep-badge">${epBadgeText}</span>
        </div>
        ${fav ? `<div class="card-fav-indicator">❤️</div>` : ""}
      </div>
      <div class="card-body">
        <div class="card-title">${item.title || item.alternative_title || "أنمي"}</div>
        <div class="card-meta">
          <span>${(item.content_type || "TV").toUpperCase()}</span>
          <span>${subLeft}</span>
        </div>
        ${progressHtml}
      </div>
    `;

    card._animeData = item;
    card.addEventListener("click", () => {
      openAnimeDetails(item._id, isHistoryCard ? item.lastEpisodeNumber : null);
    });
    card.addEventListener("focus", () => {
      setAmbientBackground(poster);
    });

    return card;
  }

  // =========================================================================
  // HOME VIEW
  // =========================================================================
  async function loadHomeView() {
    const loader = $("global-loader");
    try {
      loader.classList.remove("hidden");
      const data = await apiGet("/api/home");
      state.homeData = data;
      state.banners = data.banners || [];
      state.genresList = data.genres || [];

      renderHeroBanner(0);
      startBannerRotation();
      renderContinueWatchingRow();
      renderGenresRail();
      renderHomeSections(data.sections || []);
      renderSearchGenresBar();
      loader.classList.add("hidden");

      if (!state.focusedEl) {
        setFocus($("hero-watch-btn"));
      }
    } catch (err) {
      loader.innerHTML = `
        <p style="color:#f87171;font-weight:800;font-size:1.2rem;">تعذر الاتصال بالخادم: ${err.message}</p>
        <button class="ps5-btn primary focusable" onclick="location.reload()">إعادة المحاولة ↻</button>
      `;
    }
  }

  function renderHeroBanner(idx) {
    if (!state.banners.length) return;
    state.bannerIndex = (idx + state.banners.length) % state.banners.length;
    const b = state.banners[state.bannerIndex];

    const hero = $("hero-banner");
    const img = b.banner_picture || b.main_picture || "assets/app_logo.png";
    hero.style.backgroundImage = `url("${img}")`;
    setAmbientBackground(img);

    $("hero-title").textContent = b.title || "";
    $("hero-subtitle").textContent = b.alternative_title || "";

    const epNum = b.latest_episode_released?.episode_number;
    $("hero-badges").innerHTML = `
      <span class="badge">🔥 مميز اليوم</span>
      <span class="badge purple">${(b.content_type || "TV").toUpperCase()}</span>
      ${epNum ? `<span class="badge gold">الحلقة ${epNum} متوفرة</span>` : ""}
    `;

    updateHeroFavoriteButton();

    const dots = $("hero-dots");
    dots.innerHTML = state.banners
      .slice(0, 10)
      .map(
        (_, i) =>
          `<span class="hero-dot ${i === state.bannerIndex ? "active" : ""}"></span>`
      )
      .join("");
  }

  function updateHeroFavoriteButton() {
    const b = state.banners[state.bannerIndex];
    if (!b) return;
    const fav = isFavorite(b._id);
    const lbl = $("hero-fav-label");
    if (lbl) lbl.textContent = fav ? "محفوظ في قائمتي ❤️" : "إضافة لقائمتي";
  }

  function startBannerRotation() {
    clearInterval(state.bannerTimer);
    state.bannerTimer = setInterval(() => {
      if (state.activeTab === "home" && !state.detailsOpen && !state.playerOpen) {
        renderHeroBanner(state.bannerIndex + 1);
      }
    }, 8000);
  }

  function renderContinueWatchingRow() {
    const wrap = $("continue-watching-container");
    const rail = $("continue-watching-row");
    if (!wrap || !rail) return;

    const hist = state.userData.watch_history || [];
    if (!hist.length) {
      wrap.classList.add("hidden");
      return;
    }
    wrap.classList.remove("hidden");
    rail.innerHTML = "";
    hist.slice(0, 12).forEach((item) => {
      rail.appendChild(createAnimeCard(item, true));
    });
  }

  function renderGenresRail() {
    const rail = $("home-genres-rail");
    if (!rail) return;
    rail.innerHTML = "";
    state.genresList.forEach((g) => {
      const btn = document.createElement("button");
      btn.className = "genre-card focusable";
      btn.textContent = g.value || "تصنيف";
      btn.addEventListener("click", () => {
        switchTab("search");
        state.searchGenreId = g._id;
        state.searchPage = 1;
        highlightActiveGenreChip();
        executeSearch(false);
      });
      rail.appendChild(btn);
    });
  }

  function renderHomeSections(sections) {
    const container = $("home-sections-container");
    if (!container) return;
    container.innerHTML = "";

    sections.forEach((sec) => {
      const items = sec.items || [];
      if (!items.length) return;

      const block = document.createElement("div");
      block.className = "content-row-block";

      const title = sec.sectionTitle || sec.screenTitle || "قسم الأنمي";
      block.innerHTML = `
        <div class="row-header">
          <h2 class="row-title">${title}</h2>
        </div>
      `;

      const rail = document.createElement("div");
      rail.className = "cards-rail";
      items.forEach((anime) => {
        rail.appendChild(createAnimeCard(anime, false));
      });

      block.appendChild(rail);
      container.appendChild(block);
    });
  }

  // =========================================================================
  // SCHEDULE VIEW (الجدولة)
  // =========================================================================
  async function loadScheduleView() {
    if (!state.scheduleData) {
      try {
        showToast("جاري تحميل جدول المواعيد...");
        state.scheduleData = await apiGet("/api/schedule");
      } catch (e) {
        showToast("تعذر تحميل الجدول");
        return;
      }
    }

    const daysBar = $("schedule-days-bar");
    const grid = $("schedule-grid");
    daysBar.innerHTML = "";
    grid.innerHTML = "";

    const schedList = state.scheduleData.schedule || [];
    const dates = state.scheduleData.availableDates || [];

    if (!state.selectedScheduleDay && dates.length) {
      state.selectedScheduleDay = dates[0].dayName;
    }

    dates.forEach((d) => {
      const btn = document.createElement("button");
      const active = d.dayName === state.selectedScheduleDay;
      btn.className = `chip focusable ${active ? "active" : ""}`;
      const arName = DAY_AR[String(d.dayName).toLowerCase()] || d.dayName;
      btn.textContent = `${arName} (${d.dayOfMonth || ""})`;
      btn.addEventListener("click", () => {
        state.selectedScheduleDay = d.dayName;
        loadScheduleView();
      });
      daysBar.appendChild(btn);
    });

    // Filter schedule items for selected day
    let dayItems = [];
    if (Array.isArray(schedList)) {
      const foundGroup = schedList.find(
        (g) =>
          (g.dayName && g.dayName === state.selectedScheduleDay) ||
          (g._id && g._id.toLowerCase() === String(state.selectedScheduleDay).toLowerCase())
      );
      if (foundGroup && Array.isArray(foundGroup.items)) {
        dayItems = foundGroup.items;
      } else {
        dayItems = schedList.filter(
          (it) =>
            !it.dayName ||
            it.dayName.toLowerCase() === String(state.selectedScheduleDay).toLowerCase()
        );
      }
    }

    if (!dayItems.length && Array.isArray(schedList)) {
      // Flatten if nested or show all items
      schedList.forEach((entry) => {
        if (Array.isArray(entry.items)) dayItems.push(...entry.items);
        else if (entry._id && entry.title) dayItems.push(entry);
      });
    }

    dayItems.forEach((item) => {
      const anime = item.anime || item;
      if (anime && anime._id) {
        grid.appendChild(createAnimeCard(anime, false));
      }
    });
  }

  // =========================================================================
  // SEARCH & LIBRARY FILTER VIEW (البحث والمكتبة)
  // =========================================================================
  function renderSearchGenresBar() {
    const bar = $("search-genres-bar");
    if (!bar) return;
    bar.innerHTML = "";

    const allBtn = document.createElement("button");
    allBtn.className = `chip genre-filter-chip focusable ${!state.searchGenreId ? "active" : ""}`;
    allBtn.dataset.genreId = "";
    allBtn.textContent = "كل التصنيفات";
    allBtn.addEventListener("click", () => {
      state.searchGenreId = "";
      state.searchPage = 1;
      highlightActiveGenreChip();
      executeSearch(false);
    });
    bar.appendChild(allBtn);

    state.genresList.forEach((g) => {
      const btn = document.createElement("button");
      btn.className = `chip genre-filter-chip focusable ${state.searchGenreId === g._id ? "active" : ""}`;
      btn.dataset.genreId = g._id;
      btn.textContent = g.value;
      btn.addEventListener("click", () => {
        state.searchGenreId = g._id;
        state.searchPage = 1;
        highlightActiveGenreChip();
        executeSearch(false);
      });
      bar.appendChild(btn);
    });
  }

  function highlightActiveGenreChip() {
    document.querySelectorAll(".genre-filter-chip").forEach((el) => {
      el.classList.toggle("active", el.dataset.genreId === state.searchGenreId);
    });
  }

  async function executeSearch(append = false) {
    const grid = $("search-results-grid");
    const moreBtn = $("search-load-more");
    if (!append) {
      state.searchPage = 1;
      grid.innerHTML = `<div class="global-loader"><div class="ps5-spinner"></div><p>جاري البحث في المكتبة...</p></div>`;
    }

    const body = {
      page: state.searchPage,
      sort_by: state.searchSort,
      sort_direction: -1,
      text_direction: "ltr",
    };

    const q = $("search-input").value.trim();
    if (q) body.query = q;
    if (state.searchStatus) body.multi_release_status = [state.searchStatus];
    if (state.searchType) body.multi_content_types = [state.searchType];
    if (state.searchGenreId) body.multi_genres = [state.searchGenreId];

    try {
      const res = await apiPost("/api/search", body);
      const items = res.items || [];
      if (!append) grid.innerHTML = "";

      if (!items.length && !append) {
        grid.innerHTML = `<p style="grid-column:1/-1;text-align:center;padding:48px;color:#94a3b8;font-size:1.2rem;">لا توجد نتائج مطابقة للبحث</p>`;
        moreBtn.classList.add("hidden");
        return;
      }

      items.forEach((anime) => {
        grid.appendChild(createAnimeCard(anime, false));
      });

      if (items.length >= 15) {
        moreBtn.classList.remove("hidden");
      } else {
        moreBtn.classList.add("hidden");
      }
    } catch (e) {
      if (!append) {
        grid.innerHTML = `<p style="color:#f87171;padding:24px;">حدث خطأ أثناء البحث: ${e.message}</p>`;
      }
    }
  }

  // =========================================================================
  // FAVORITES & WATCH HISTORY VIEWS
  // =========================================================================
  function renderFavoritesView() {
    const grid = $("favorites-grid");
    if (!grid) return;
    grid.innerHTML = "";
    const favs = state.userData.favorites || [];
    if (!favs.length) {
      grid.innerHTML = `<p style="grid-column:1/-1;text-align:center;padding:60px;color:#94a3b8;font-size:1.2rem;">قائمتك فارغة حالياً. اضغط على زر (□) على أي أنمي لإضافته هنا!</p>`;
      return;
    }
    favs.forEach((item) => grid.appendChild(createAnimeCard(item, false)));
  }

  function renderHistoryView() {
    const grid = $("history-grid");
    if (!grid) return;
    grid.innerHTML = "";
    const hist = state.userData.watch_history || [];
    if (!hist.length) {
      grid.innerHTML = `<p style="grid-column:1/-1;text-align:center;padding:60px;color:#94a3b8;font-size:1.2rem;">لا يوجد سجل مشاهدات حتى الآن.</p>`;
      return;
    }
    hist.forEach((item) => grid.appendChild(createAnimeCard(item, true)));
  }

  // =========================================================================
  // ANIME DETAILS & EPISODES MODAL
  // =========================================================================
  async function openAnimeDetails(animeId, autoResumeEpNum = null) {
    if (!animeId) return;
    state.lastFocusBeforeDetails = state.focusedEl;
    state.detailsOpen = true;
    const modal = $("details-modal");
    modal.classList.remove("hidden");

    $("details-title").textContent = "جاري التحميل...";
    $("details-alt-title").textContent = "";
    $("details-synopsis").textContent = "جاري جلب تفاصيل الأنمي والحلقات...";
    $("episodes-grid").innerHTML = `<div class="global-loader"><div class="ps5-spinner"></div></div>`;

    setFocus($("details-back-btn"));

    try {
      const [detailsRes, epsRes] = await Promise.all([
        apiGet(`/api/details/${animeId}`),
        apiGet(`/api/episodes/${animeId}?sort=-1`),
      ]);

      const item = detailsRes.item || {};
      state.currentAnime = item;
      state.currentEpisodes = epsRes.items || [];
      state.epSortAsc = false;
      state.epRangeIndex = 0;

      const poster =
        item.main_picture || item.large_picture || item.medium_picture || "assets/app_logo.png";
      const backdrop =
        (item.gallery && item.gallery[0]) ||
        (item.pictures && item.pictures[0]) ||
        poster;

      $("details-poster").src = poster;
      $("details-backdrop").style.backgroundImage = `url("${backdrop}")`;
      $("details-title").textContent = item.title || "";
      $("details-alt-title").textContent =
        item.alternative_title || item.native_title || "";

      const rating = item.myAnimeList_rating
        ? `★ MAL ${Number(item.myAnimeList_rating).toFixed(2)}`
        : "★ جديد";
      $("details-badges").innerHTML = `
        <span class="badge gold">${rating}</span>
        <span class="badge purple">${(item.content_type || "TV").toUpperCase()}</span>
        ${item.release_year ? `<span class="badge">${item.release_year}</span>` : ""}
        ${item.ageRating ? `<span class="badge">${String(item.ageRating).toUpperCase()}</span>` : ""}
        <span class="badge green">${item.available_episodes || state.currentEpisodes.length} حلقة</span>
      `;

      const genres = item.genreLabels || [];
      $("details-genres").innerHTML = genres
        .map((g) => `<span class="genre-pill">${g.label}</span>`)
        .join("");

      $("details-synopsis").textContent =
        item.synopsis || "لا يتوفر ملخص قصة لهذا الأنمي حالياً.";

      const bcast = $("details-broadcast");
      if (item.nextBroadCastAtLabel) {
        bcast.textContent = item.nextBroadCastAtLabel;
        bcast.classList.remove("hidden");
      } else {
        bcast.classList.add("hidden");
      }

      updateDetailsFavoriteButton();
      renderEpisodesSection();

      // Determine target episode for primary CTA button
      let targetEp = state.currentEpisodes[state.currentEpisodes.length - 1];
      const histItem = state.userData.watch_history.find((x) => x._id === item._id);
      if (autoResumeEpNum) {
        const found = state.currentEpisodes.find(
          (e) => e.episode_number === autoResumeEpNum
        );
        if (found) targetEp = found;
      } else if (histItem && histItem.lastEpisodeNumber) {
        const found = state.currentEpisodes.find(
          (e) => e.episode_number === histItem.lastEpisodeNumber
        );
        if (found) targetEp = found;
      }

      const playBtn = $("details-play-first-btn");
      const playLbl = $("details-play-btn-label");
      if (targetEp) {
        playLbl.textContent = `تشغيل الحلقة ${targetEp.episode_number} ▶`;
        playBtn.onclick = () => startEpisodePlayback(targetEp);
      } else {
        playLbl.textContent = "لا توجد حلقات متاحة";
        playBtn.onclick = null;
      }

      setFocus(playBtn);
    } catch (e) {
      $("details-synopsis").textContent = `تعذر جلب البيانات: ${e.message}`;
    }
  }

  function updateDetailsFavoriteButton() {
    if (!state.currentAnime) return;
    const fav = isFavorite(state.currentAnime._id);
    const lbl = $("details-fav-label");
    if (lbl) lbl.textContent = fav ? "محفوظ في قائمتي ❤️" : "إضافة لقائمتي";
  }

  function renderEpisodesSection() {
    const eps = [...state.currentEpisodes];
    if (state.epSortAsc) {
      eps.sort((a, b) => (a.episode_number || 0) - (b.episode_number || 0));
    } else {
      eps.sort((a, b) => (b.episode_number || 0) - (a.episode_number || 0));
    }

    $("episodes-count-title").textContent = `الحلقات المتوفرة (${eps.length})`;

    const rangesBar = $("episodes-ranges-bar");
    rangesBar.innerHTML = "";
    const totalPages = Math.ceil(eps.length / state.epPageSize);

    if (totalPages > 1) {
      for (let i = 0; i < totalPages; i++) {
        const chunk = eps.slice(i * state.epPageSize, (i + 1) * state.epPageSize);
        const firstNum = chunk[0]?.episode_number;
        const lastNum = chunk[chunk.length - 1]?.episode_number;
        const btn = document.createElement("button");
        btn.className = `chip focusable ${i === state.epRangeIndex ? "active" : ""}`;
        btn.textContent = `${firstNum} - ${lastNum}`;
        btn.addEventListener("click", () => {
          state.epRangeIndex = i;
          renderEpisodesSection();
        });
        rangesBar.appendChild(btn);
      }
    }

    const visibleEps = eps.slice(
      state.epRangeIndex * state.epPageSize,
      (state.epRangeIndex + 1) * state.epPageSize
    );

    const grid = $("episodes-grid");
    grid.innerHTML = "";

    const fallbackThumb =
      state.currentAnime?.thumbnail_picture ||
      state.currentAnime?.main_picture ||
      "assets/app_logo.png";

    visibleEps.forEach((ep) => {
      const card = document.createElement("div");
      card.className = "episode-card focusable";
      card.tabIndex = 0;

      const thumb = ep.thumbnail || fallbackThumb;
      const progKey = `${state.currentAnime?._id}_${ep.episode_number}`;
      const prog = state.userData.progress[progKey];
      const pct =
        prog && prog.duration > 0
          ? Math.min(100, Math.round((prog.currentTime / prog.duration) * 100))
          : 0;

      card.innerHTML = `
        <div class="ep-thumb-wrap">
          <img class="ep-thumb" src="${thumb}" alt="الحلقة ${ep.episode_number}" loading="lazy" onerror="this.src='assets/app_logo.png'" />
          <span class="ep-num-badge">الحلقة ${ep.episode_number}</span>
          ${ep.is_filler ? `<span class="ep-filler-badge">فلر Filler</span>` : ""}
          ${ep.is_recap ? `<span class="ep-filler-badge">ملخص Recap</span>` : ""}
        </div>
        <div class="ep-body">
          <div class="ep-title">الحلقة ${ep.episode_number}</div>
          <div class="ep-sub">
            ${ep.duration ? `${Math.round(ep.duration / 60)} دقيقة` : "مترجمة للعربية"}
            ${prog ? ` • شوهد ${formatTime(prog.currentTime)}` : ""}
          </div>
          ${
            pct > 0
              ? `<div class="card-progress-bar"><div class="card-progress-fill" style="width:${pct}%"></div></div>`
              : ""
          }
        </div>
      `;

      card.addEventListener("click", () => startEpisodePlayback(ep));
      grid.appendChild(card);
    });
  }

  function closeAnimeDetails() {
    state.detailsOpen = false;
    $("details-modal").classList.add("hidden");
    renderContinueWatchingRow();
    if (state.lastFocusBeforeDetails && document.body.contains(state.lastFocusBeforeDetails)) {
      setFocus(state.lastFocusBeforeDetails);
    } else {
      setFocus($("tab-" + state.activeTab));
    }
  }

  // =========================================================================
  // FULLSCREEN PS5 VIDEO PLAYER
  // =========================================================================
  async function startEpisodePlayback(ep) {
    if (!ep || !state.currentAnime) return;
    state.lastFocusBeforePlayer = state.focusedEl;
    state.playerOpen = true;
    state.playingEpisode = ep;

    const modal = $("player-modal");
    modal.classList.remove("hidden");
    showPlayerHud();

    $("player-anime-title").textContent = state.currentAnime.title || "";
    $("player-ep-title").textContent = `الحلقة ${ep.episode_number}`;
    $("player-servers-list").innerHTML = "";
    showPlayerSpinner("جاري جلب سيرفرات المشاهدة...");

    setFocus($("player-play-pause"));

    try {
      const res = await apiPost("/api/sources", {
        animeId: state.currentAnime._id,
        episodeId: ep._id,
        episode_number: ep.episode_number,
      });

      const rawItems = res.items || [];
      // Build flat list of (source, quality) options prioritized by CR2 / BBZ & 1080P / 720P
      const options = [];
      rawItems.forEach((src) => {
        const quals = src.qualities && src.qualities.length ? src.qualities : ["720P"];
        quals.forEach((q) => {
          options.push({
            sourceId: src._id,
            serverName: src.server_name || src.provider || "Server",
            provider: src.provider || "",
            quality: q,
            subTitle: src.sub_title || "ar_sub",
          });
        });
      });

      // Sort so fast direct servers (CR2, BBZ) and higher resolutions come first
      options.sort((a, b) => {
        const score = (o) => {
          let s = 0;
          if (o.serverName === "CR2") s += 100;
          else if (o.serverName === "BBZ") s += 90;
          if (String(o.quality).includes("1080")) s += 30;
          else if (String(o.quality).includes("720")) s += 20;
          return s;
        };
        return score(b) - score(a);
      });

      state.episodeSources = options;
      if (!options.length) {
        showPlayerSpinner("لا توجد سيرفرات متاحة لهذه الحلقة حالياً");
        return;
      }

      renderPlayerServerButtons();
      await loadStreamFromOption(0);
    } catch (e) {
      showPlayerSpinner(`خطأ في جلب السيرفرات: ${e.message}`);
    }
  }

  function renderPlayerServerButtons() {
    const list = $("player-servers-list");
    list.innerHTML = "";
    state.episodeSources.forEach((opt, idx) => {
      const btn = document.createElement("button");
      btn.className = `chip focusable ${idx === state.selectedSourceIndex ? "active" : ""}`;
      btn.textContent = `${opt.serverName} • ${opt.quality}`;
      btn.addEventListener("click", () => {
        loadStreamFromOption(idx);
      });
      list.appendChild(btn);
    });
  }

  async function loadStreamFromOption(index, autoFallbackCount = 0) {
    if (index < 0 || index >= state.episodeSources.length) return;
    state.selectedSourceIndex = index;
    renderPlayerServerButtons();

    const opt = state.episodeSources[index];
    $("player-active-badge").textContent = `${opt.serverName} • ${opt.quality}`;
    showPlayerSpinner(`جاري الاتصال بسيرفر ${opt.serverName} (${opt.quality})...`);

    const video = $("ps5-video");
    const progKey = `${state.currentAnime?._id}_${state.playingEpisode?.episode_number}`;
    const savedProg = state.userData.progress[progKey];
    const resumeTime =
      video.currentTime > 5
        ? video.currentTime
        : savedProg && savedProg.currentTime > 5 && savedProg.currentTime < (savedProg.duration || 9999) - 30
        ? savedProg.currentTime
        : 0;

    try {
      const playData = await apiPost("/api/play", {
        sourceId: opt.sourceId,
        episodeId: state.playingEpisode._id,
        quality: opt.quality,
      });

      const streamUrl = playData.proxyUrl || playData.videoUrl;
      const directUrl = playData.videoUrl;
      if (!streamUrl) {
        throw new Error("لم يتم استلام رابط البث");
      }

      destroyHls();

      const isHls =
        playData.is_hls ||
        String(directUrl).toLowerCase().includes(".m3u8");

      if (isHls && window.Hls && window.Hls.isSupported()) {
        const hls = new window.Hls({
          enableWorker: true,
          maxBufferLength: 30,
        });
        state.hlsInstance = hls;
        hls.loadSource(streamUrl);
        hls.attachMedia(video);
        hls.on(window.Hls.Events.MANIFEST_PARSED, () => {
          hidePlayerSpinner();
          if (resumeTime > 0) video.currentTime = resumeTime;
          video.play().catch(() => {});
        });
        hls.on(window.Hls.Events.ERROR, (_, data) => {
          if (data.fatal && autoFallbackCount < 4) {
            showToast(`جاري التحويل للسيرفر البديل...`);
            loadStreamFromOption((index + 1) % state.episodeSources.length, autoFallbackCount + 1);
          }
        });
      } else {
        video.src = streamUrl;
        video.onloadedmetadata = () => {
          hidePlayerSpinner();
          if (resumeTime > 0) video.currentTime = resumeTime;
          video.play().catch(() => {});
        };
        video.onerror = () => {
          // Try direct URL if proxy failed, or next server
          if (video.src !== directUrl && directUrl) {
            video.src = directUrl;
            video.play().catch(() => {});
          } else if (autoFallbackCount < 4 && state.episodeSources.length > 1) {
            showToast(`جاري التحويل للسيرفر البديل...`);
            loadStreamFromOption((index + 1) % state.episodeSources.length, autoFallbackCount + 1);
          }
        };
      }
    } catch (e) {
      if (autoFallbackCount < 4 && state.episodeSources.length > 1) {
        loadStreamFromOption((index + 1) % state.episodeSources.length, autoFallbackCount + 1);
      } else {
        showPlayerSpinner(`تعذر تشغيل السيرفر، اختر سيرفر آخر بـ (△)`);
      }
    }
  }

  function destroyHls() {
    if (state.hlsInstance) {
      try {
        state.hlsInstance.destroy();
      } catch (e) {}
      state.hlsInstance = null;
    }
  }

  function showPlayerSpinner(msg) {
    const sp = $("player-spinner");
    const txt = $("player-status-text");
    if (txt && msg) txt.textContent = msg;
    if (sp) sp.classList.remove("hidden");
  }

  function hidePlayerSpinner() {
    const sp = $("player-spinner");
    if (sp) sp.classList.add("hidden");
  }

  function showPlayerHud() {
    const hud = $("player-hud");
    if (!hud) return;
    hud.classList.remove("hud-hidden");
    clearTimeout(state.hudTimer);
    state.hudTimer = setTimeout(() => {
      const video = $("ps5-video");
      if (state.playerOpen && video && !video.paused) {
        hud.classList.add("hud-hidden");
      }
    }, 5500);
  }

  function togglePlayPause() {
    const video = $("ps5-video");
    if (!video) return;
    showPlayerHud();
    if (video.paused) {
      video.play().catch(() => {});
    } else {
      video.pause();
    }
  }

  function seekVideo(deltaSec) {
    const video = $("ps5-video");
    if (!video || !video.duration) return;
    showPlayerHud();
    video.currentTime = Math.max(0, Math.min(video.duration, video.currentTime + deltaSec));
  }

  function cyclePlayerServer() {
    if (!state.episodeSources.length) return;
    showPlayerHud();
    const nextIdx = (state.selectedSourceIndex + 1) % state.episodeSources.length;
    loadStreamFromOption(nextIdx);
  }

  function playAdjacentEpisode(offset) {
    if (!state.playingEpisode || !state.currentEpisodes.length) return;
    const targetNum = state.playingEpisode.episode_number + offset;
    const found = state.currentEpisodes.find((e) => e.episode_number === targetNum);
    if (found) {
      showToast(`تشغيل الحلقة ${found.episode_number}`);
      startEpisodePlayback(found);
    } else {
      showToast(offset > 0 ? "هذه آخر حلقة متوفرة" : "هذه الحلقة الأولى");
    }
  }

  function closeVideoPlayer() {
    const video = $("ps5-video");
    if (video) {
      if (state.currentAnime && state.playingEpisode && video.currentTime > 3) {
        recordWatchProgress(
          state.currentAnime,
          state.playingEpisode,
          video.currentTime,
          video.duration
        );
      }
      video.pause();
      video.removeAttribute("src");
      video.load();
    }
    destroyHls();
    state.playerOpen = false;
    $("player-modal").classList.add("hidden");
    $("skip-segment-btn").classList.add("hidden");
    if (state.detailsOpen) {
      renderEpisodesSection();
    }
    if (state.lastFocusBeforePlayer && document.body.contains(state.lastFocusBeforePlayer)) {
      setFocus(state.lastFocusBeforePlayer);
    } else {
      setFocus($("details-play-first-btn"));
    }
  }

  function setupVideoEvents() {
    const video = $("ps5-video");
    if (!video) return;

    video.addEventListener("play", () => {
      $("player-play-icon").textContent = "⏸ إيقاف مؤقت";
      showPlayerHud();
    });

    video.addEventListener("pause", () => {
      $("player-play-icon").textContent = "▶ تشغيل";
      showPlayerHud();
    });

    video.addEventListener("waiting", () => showPlayerSpinner("جاري التحميل..."));
    video.addEventListener("playing", () => hidePlayerSpinner());

    video.addEventListener("timeupdate", () => {
      const cur = video.currentTime || 0;
      const dur = video.duration || 0;
      $("player-time-current").textContent = formatTime(cur);
      $("player-time-total").textContent = formatTime(dur);

      if (dur > 0) {
        $("player-progress-fill").style.width = `${(cur / dur) * 100}%`;
        if (video.buffered.length > 0) {
          const bufEnd = video.buffered.end(video.buffered.length - 1);
          $("player-progress-buffer").style.width = `${Math.min(100, (bufEnd / dur) * 100)}%`;
        }
      }

      // Check Intro / Outro timestamps from Anime Rift API
      const ep = state.playingEpisode;
      const skipBtn = $("skip-segment-btn");
      const skipLbl = $("skip-segment-label");
      const introMarker = $("player-intro-marker");
      const outroMarker = $("player-outro-marker");

      if (ep && dur > 0) {
        const intro = ep.intro;
        const outro = ep.outro;

        if (intro && intro.end > intro.start) {
          introMarker.style.left = `${(intro.start / dur) * 100}%`;
          introMarker.style.width = `${((intro.end - intro.start) / dur) * 100}%`;
          introMarker.classList.remove("hidden");
        } else {
          introMarker.classList.add("hidden");
        }

        if (outro && outro.end > outro.start) {
          outroMarker.style.left = `${(outro.start / dur) * 100}%`;
          outroMarker.style.width = `${((outro.end - outro.start) / dur) * 100}%`;
          outroMarker.classList.remove("hidden");
        } else {
          outroMarker.classList.add("hidden");
        }

        if (intro && cur >= intro.start && cur < intro.end - 1) {
          skipLbl.textContent = "تخطي البداية ⏭";
          skipBtn.classList.remove("hidden");
          skipBtn._targetTime = intro.end;
        } else if (outro && cur >= outro.start && cur < outro.end - 1) {
          skipLbl.textContent = "تخطي النهاية ⏭";
          skipBtn.classList.remove("hidden");
          skipBtn._targetTime = outro.end;
        } else {
          skipBtn.classList.add("hidden");
          skipBtn._targetTime = null;
        }
      }

      // Periodic progress save every 5 seconds
      if (!video._lastSave || Date.now() - video._lastSave > 5000) {
        video._lastSave = Date.now();
        recordWatchProgress(state.currentAnime, state.playingEpisode, cur, dur);
      }
    });

    video.addEventListener("ended", () => {
      playAdjacentEpisode(1);
    });

    $("skip-segment-btn").addEventListener("click", () => {
      const target = $("skip-segment-btn")._targetTime;
      if (target != null) {
        video.currentTime = target;
        showToast("تم التخطي ⏭");
      }
    });

    $("player-progress-track").addEventListener("click", (e) => {
      if (!video.duration) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      video.currentTime = ratio * video.duration;
    });
  }

  // =========================================================================
  // TAB NAVIGATION
  // =========================================================================
  function switchTab(tabName) {
    if (!state.tabsOrder.includes(tabName)) return;
    state.activeTab = tabName;

    document.querySelectorAll(".nav-tab").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === tabName);
    });

    document.querySelectorAll(".view-section").forEach((sec) => {
      sec.classList.toggle("hidden", sec.id !== `view-${tabName}`);
      sec.classList.toggle("active", sec.id === `view-${tabName}`);
    });

    if (tabName === "home") {
      renderContinueWatchingRow();
    } else if (tabName === "schedule") {
      loadScheduleView();
    } else if (tabName === "search") {
      if (!state.searchResults.length && !$("search-results-grid").children.length) {
        executeSearch(false);
      }
    } else if (tabName === "favorites") {
      renderFavoritesView();
    } else if (tabName === "history") {
      renderHistoryView();
    }
  }

  // =========================================================================
  // SPATIAL 2D FOCUS & DUALSENSE CONTROLLER ENGINE
  // =========================================================================
  function getActiveScopeElement() {
    if (state.playerOpen) return $("player-modal");
    if (state.detailsOpen) return $("details-modal");
    return document.body;
  }

  function getVisibleFocusables() {
    const scope = getActiveScopeElement();
    const all = Array.from(scope.querySelectorAll(".focusable"));
    return all.filter((el) => {
      if (el.disabled || el.classList.contains("hidden")) return false;
      const style = window.getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
        return false;
      }
      const rect = el.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    });
  }

  function setFocus(el, scroll = true) {
    if (!el) return;
    if (state.focusedEl && state.focusedEl !== el) {
      state.focusedEl.classList.remove("ps5-focused");
    }
    state.focusedEl = el;
    el.classList.add("ps5-focused");
    el.focus({ preventScroll: true });

    if (scroll && !state.playerOpen) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
    }
  }

  function moveFocusSpatial(dir) {
    if (state.playerOpen) {
      showPlayerHud();
    }

    const candidates = getVisibleFocusables();
    if (!candidates.length) return;

    if (!state.focusedEl || !candidates.includes(state.focusedEl)) {
      setFocus(candidates[0]);
      return;
    }

    const curRect = state.focusedEl.getBoundingClientRect();
    const curCx = curRect.left + curRect.width / 2;
    const curCy = curRect.top + curRect.height / 2;

    let bestEl = null;
    let bestScore = Infinity;

    for (const el of candidates) {
      if (el === state.focusedEl) continue;
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dx = cx - curCx;
      const dy = cy - curCy;

      if (dir === "left" && dx >= -8) continue;
      if (dir === "right" && dx <= 8) continue;
      if (dir === "up" && dy >= -8) continue;
      if (dir === "down" && dy <= 8) continue;

      const primaryDist = dir === "left" || dir === "right" ? Math.abs(dx) : Math.abs(dy);
      const orthoDist = dir === "left" || dir === "right" ? Math.abs(dy) : Math.abs(dx);

      // Weight orthogonal distance more heavily so D-pad stays on the same row/column
      const score = primaryDist + orthoDist * 2.6;
      if (score < bestScore) {
        bestScore = score;
        bestEl = el;
      }
    }

    if (bestEl) {
      setFocus(bestEl);
    }
  }

  function handleActionButton(action) {
    if (action === "cross") {
      if (state.playerOpen) {
        const hud = $("player-hud");
        if (hud.classList.contains("hud-hidden")) {
          showPlayerHud();
          togglePlayPause();
          return;
        }
      }
      if (state.focusedEl) {
        state.focusedEl.click();
      }
    } else if (action === "circle") {
      if (state.playerOpen) {
        closeVideoPlayer();
      } else if (state.detailsOpen) {
        closeAnimeDetails();
      } else if (state.activeTab !== "home") {
        switchTab("home");
        setFocus($("tab-home"));
      }
    } else if (action === "square") {
      if (state.playerOpen) return;
      if (state.detailsOpen && state.currentAnime) {
        toggleFavorite(state.currentAnime);
      } else if (state.focusedEl && state.focusedEl._animeData) {
        toggleFavorite(state.focusedEl._animeData);
      } else if (state.activeTab === "home" && state.banners[state.bannerIndex]) {
        toggleFavorite(state.banners[state.bannerIndex]);
      }
    } else if (action === "triangle") {
      if (state.playerOpen) {
        cyclePlayerServer();
      } else {
        if (state.detailsOpen) closeAnimeDetails();
        switchTab("search");
        setFocus($("search-input"));
      }
    } else if (action === "l1") {
      if (state.playerOpen) {
        playAdjacentEpisode(-1);
      } else if (!state.detailsOpen) {
        const idx = state.tabsOrder.indexOf(state.activeTab);
        const nextTab = state.tabsOrder[(idx - 1 + state.tabsOrder.length) % state.tabsOrder.length];
        switchTab(nextTab);
        setFocus($("tab-" + nextTab));
      }
    } else if (action === "r1") {
      if (state.playerOpen) {
        const skipBtn = $("skip-segment-btn");
        if (skipBtn && !skipBtn.classList.contains("hidden") && skipBtn._targetTime != null) {
          skipBtn.click();
        } else {
          playAdjacentEpisode(1);
        }
      } else if (!state.detailsOpen) {
        const idx = state.tabsOrder.indexOf(state.activeTab);
        const nextTab = state.tabsOrder[(idx + 1) % state.tabsOrder.length];
        switchTab(nextTab);
        setFocus($("tab-" + nextTab));
      }
    } else if (action === "l2") {
      if (state.playerOpen) seekVideo(-10);
    } else if (action === "r2") {
      if (state.playerOpen) seekVideo(10);
    }
  }

  // DualSense Gamepad Polling Loop (60fps)
  const gpState = {
    lastButtons: {},
    lastStickTime: 0,
  };

  function pollGamepad() {
    const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
    let activePad = null;
    for (const gp of gamepads) {
      if (gp && gp.connected) {
        activePad = gp;
        break;
      }
    }

    if (activePad) {
      const txt = $("gamepad-text");
      if (txt) txt.textContent = "DualSense متصل 🎮";

      const now = performance.now();
      const b = activePad.buttons;

      const checkBtn = (idx, name) => {
        const pressed = b[idx] && b[idx].pressed;
        if (pressed && !gpState.lastButtons[idx]) {
          gpState.lastButtons[idx] = true;
          return true;
        } else if (!pressed) {
          gpState.lastButtons[idx] = false;
        }
        return false;
      };

      if (checkBtn(0)) handleActionButton("cross");
      if (checkBtn(1)) handleActionButton("circle");
      if (checkBtn(2)) handleActionButton("square");
      if (checkBtn(3)) handleActionButton("triangle");
      if (checkBtn(4)) handleActionButton("l1");
      if (checkBtn(5)) handleActionButton("r1");
      if (checkBtn(6)) handleActionButton("l2");
      if (checkBtn(7)) handleActionButton("r2");

      if (checkBtn(12)) moveFocusSpatial("up");
      if (checkBtn(13)) moveFocusSpatial("down");
      if (checkBtn(14)) moveFocusSpatial("left");
      if (checkBtn(15)) moveFocusSpatial("right");

      // Left Analog Stick Navigation
      const axX = activePad.axes[0] || 0;
      const axY = activePad.axes[1] || 0;
      if (now - gpState.lastStickTime > 190) {
        if (axX < -0.55) {
          moveFocusSpatial("left");
          gpState.lastStickTime = now;
        } else if (axX > 0.55) {
          moveFocusSpatial("right");
          gpState.lastStickTime = now;
        } else if (axY < -0.55) {
          moveFocusSpatial("up");
          gpState.lastStickTime = now;
        } else if (axY > 0.55) {
          moveFocusSpatial("down");
          gpState.lastStickTime = now;
        }
      }
    }

    requestAnimationFrame(pollGamepad);
  }

  // Keyboard / Remote Fallback
  function setupKeyboardAndMouse() {
    window.addEventListener("keydown", (e) => {
      const activeTag = document.activeElement?.tagName;
      const isInput = activeTag === "INPUT" || activeTag === "TEXTAREA";

      if (e.key === "ArrowUp") {
        e.preventDefault();
        moveFocusSpatial("up");
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        moveFocusSpatial("down");
      } else if (e.key === "ArrowLeft") {
        if (!isInput) {
          e.preventDefault();
          moveFocusSpatial("left");
        }
      } else if (e.key === "ArrowRight") {
        if (!isInput) {
          e.preventDefault();
          moveFocusSpatial("right");
        }
      } else if (e.key === "Enter") {
        if (isInput && document.activeElement.id === "search-input") {
          executeSearch(false);
        } else {
          e.preventDefault();
          handleActionButton("cross");
        }
      } else if (e.key === "Escape" || e.key === "Backspace") {
        if (!isInput) {
          e.preventDefault();
          handleActionButton("circle");
        }
      } else if (!isInput && (e.key === "f" || e.key === "F")) {
        handleActionButton("square");
      } else if (!isInput && (e.key === "s" || e.key === "S")) {
        handleActionButton("triangle");
      } else if (!isInput && e.key === "q") {
        handleActionButton("l1");
      } else if (!isInput && e.key === "e") {
        handleActionButton("r1");
      }
    });

    document.addEventListener("mousemove", () => {
      if (state.playerOpen) showPlayerHud();
    });
  }

  // =========================================================================
  // UI WIRING & INITIALIZATION
  // =========================================================================
  function bindStaticControls() {
    // Top Navigation Tabs
    document.querySelectorAll(".nav-tab").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    // Hero Banner Buttons
    $("hero-watch-btn").addEventListener("click", () => {
      const b = state.banners[state.bannerIndex];
      if (b) openAnimeDetails(b._id);
    });
    $("hero-fav-btn").addEventListener("click", () => {
      const b = state.banners[state.bannerIndex];
      if (b) toggleFavorite(b);
    });
    $("hero-prev-banner").addEventListener("click", () => {
      renderHeroBanner(state.bannerIndex - 1);
      startBannerRotation();
    });
    $("hero-next-banner").addEventListener("click", () => {
      renderHeroBanner(state.bannerIndex + 1);
      startBannerRotation();
    });

    // Search & Filters
    $("search-submit-btn").addEventListener("click", () => executeSearch(false));
    $("search-clear-btn").addEventListener("click", () => {
      $("search-input").value = "";
      state.searchGenreId = "";
      state.searchStatus = "";
      state.searchType = "";
      highlightActiveGenreChip();
      executeSearch(false);
    });

    document.querySelectorAll("#quick-search-tags .chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        $("search-input").value = chip.dataset.q;
        executeSearch(false);
      });
    });

    document.querySelectorAll(".filter-sort").forEach((chip) => {
      chip.addEventListener("click", () => {
        document.querySelectorAll(".filter-sort").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        state.searchSort = chip.dataset.sort;
        executeSearch(false);
      });
    });

    document.querySelectorAll(".filter-status").forEach((chip) => {
      chip.addEventListener("click", () => {
        document.querySelectorAll(".filter-status").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        state.searchStatus = chip.dataset.status;
        executeSearch(false);
      });
    });

    document.querySelectorAll(".filter-type").forEach((chip) => {
      chip.addEventListener("click", () => {
        document.querySelectorAll(".filter-type").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        state.searchType = chip.dataset.type;
        executeSearch(false);
      });
    });

    $("search-load-more").addEventListener("click", () => {
      state.searchPage += 1;
      executeSearch(true);
    });

    // Clear Watch History
    $("clear-history-btn").addEventListener("click", () => {
      state.userData.watch_history = [];
      state.userData.progress = {};
      saveUserData();
      renderHistoryView();
      renderContinueWatchingRow();
      showToast("تم مسح سجل المشاهدات");
    });

    // Details Modal Buttons
    $("details-back-btn").addEventListener("click", closeAnimeDetails);
    $("details-fav-btn").addEventListener("click", () => {
      if (state.currentAnime) toggleFavorite(state.currentAnime);
    });
    $("details-sort-ep-btn").addEventListener("click", (e) => {
      state.epSortAsc = !state.epSortAsc;
      e.currentTarget.textContent = state.epSortAsc
        ? "ترتيب الحلقات: الأقدم ⇅"
        : "ترتيب الحلقات: الأحدث ⇅";
      state.epRangeIndex = 0;
      renderEpisodesSection();
    });
    $("ep-jump-input").addEventListener("change", (e) => {
      const num = parseInt(e.target.value, 10);
      if (!num || !state.currentEpisodes.length) return;
      const found = state.currentEpisodes.find((x) => x.episode_number === num);
      if (found) {
        startEpisodePlayback(found);
      } else {
        showToast(`الحلقة ${num} غير موجودة`);
      }
    });

    // Video Player Controls
    $("player-close-btn").addEventListener("click", closeVideoPlayer);
    $("player-play-pause").addEventListener("click", togglePlayPause);
    $("player-seek-back").addEventListener("click", () => seekVideo(-10));
    $("player-seek-fwd").addEventListener("click", () => seekVideo(10));
    $("player-prev-ep").addEventListener("click", () => playAdjacentEpisode(-1));
    $("player-next-ep").addEventListener("click", () => playAdjacentEpisode(1));

    // Clock
    const updateClock = () => {
      const now = new Date();
      $("clock-display").textContent = now.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
    };
    updateClock();
    setInterval(updateClock, 15000);
  }

  async function init() {
    bindStaticControls();
    setupVideoEvents();
    setupKeyboardAndMouse();
    requestAnimationFrame(pollGamepad);
    await loadUserData();
    await loadHomeView();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
