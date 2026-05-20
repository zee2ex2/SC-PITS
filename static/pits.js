(function() {
  var theme = localStorage.getItem("theme");
  if (theme) {
    document.documentElement.className = theme;
    document.cookie = "pref_theme=" + theme + "; SameSite=Lax; Path=/; Max-Age=" + (86400 * 365);
  }
})();

function setCookie(name, value, days) {
  document.cookie = name + "=" + value + "; SameSite=Lax; Path=/; Max-Age=" + (days * 86400);
}

function toggleTheme() {
  var html = document.documentElement;
  var theme = html.className === "light" ? "dark" : "light";
  html.className = theme;
  localStorage.setItem("theme", theme);
  setCookie("pref_theme", theme, 365);
}

function changePerPage(sel) {
  var n = sel.options[sel.selectedIndex].text.split(" ")[0];
  if (n) setCookie("pref_per_page", n, 365);
  location.href = sel.value;
}

function itemAutocomplete(input) {
  document.getElementById("item-id").value = "";
  var val = input.value.trim().toLowerCase();
  var container = document.getElementById("item-suggestions");
  var sel = -1;
  if (!container || val.length === 0) {
    if (container) container.style.display = "none";
    return;
  }
  var matches = (window.ADD_ITEMS || []).filter(function(item) {
    return item.name.toLowerCase().indexOf(val) === 0;
  }).slice(0, 5);
  container.innerHTML = "";
  if (matches.length === 0) {
    container.style.display = "none";
    return;
  }
  matches.forEach(function(item, i) {
    var div = document.createElement("div");
    div.className = "suggestion-item";
    div.textContent = item.name;
    div.dataset.idx = i;
    div.dataset.id = item.id;
    div.addEventListener("click", function() {
      input.value = item.name;
      document.getElementById("item-id").value = item.id;
      container.style.display = "none";
    });
    container.appendChild(div);
  });
  container.style.display = "block";
  input._itemAuto = { matches: matches, container: container, sel: 0 };
  var first = container.querySelector('.suggestion-item');
  if (first) first.classList.add('highlighted');

  if (!input._itemAutoKeydown) {
    input._itemAutoKeydown = true;
    function autoItemHighlight(i) {
      var state = input._itemAuto;
      if (!state) return;
      state.container.querySelectorAll(".suggestion-item").forEach(function(d, idx) {
        d.classList.toggle("highlighted", idx === i);
      });
      state.sel = i;
    }
    function autoItemPick(i) {
      var state = input._itemAuto;
      if (!state || i < 0 || i >= state.matches.length) return;
      input.value = state.matches[i].name;
      document.getElementById("item-id").value = state.matches[i].id;
      state.container.style.display = "none";
    }
    input.addEventListener("keydown", function(e) {
      var state = input._itemAuto;
      if (!state || state.container.style.display !== "block") return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        autoItemHighlight(state.sel === -1 ? 0 : Math.min(state.sel + 1, state.matches.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        autoItemHighlight(state.sel === -1 ? 0 : Math.max(state.sel - 1, 0));
      } else if (e.key === "Enter" && state.sel >= 0) {
        e.preventDefault();
        autoItemPick(state.sel);
      }
    });
    input.addEventListener("blur", function() {
      var state = input._itemAuto;
      if (state && state.sel >= 0) autoItemPick(state.sel);
    });
  }
}

function stationAutocomplete(input) {
  var wrap = input.closest(".autocomplete-wrap");
  if (!wrap) return;
  var hidden = wrap.querySelector(".station-id");
  if (hidden) hidden.value = "";
  var container = wrap.querySelector(".search-suggestions");
  if (!container || input.value.trim().length === 0) {
    if (container) container.style.display = "none";
    return;
  }
  var val = input.value.trim().toLowerCase();
  var matches = (window.ADD_STATIONS || []).filter(function(s) {
    return s.name.toLowerCase().indexOf(val) === 0;
  }).slice(0, 5);
  container.innerHTML = "";
  if (matches.length === 0) {
    container.style.display = "none";
    return;
  }
  matches.forEach(function(s, i) {
    var div = document.createElement("div");
    div.className = "suggestion-item";
    div.textContent = s.name;
    div.dataset.idx = i;
    div.dataset.id = s.id;
    div.addEventListener("click", function() {
      input.value = s.name;
      if (hidden) hidden.value = s.id;
      container.style.display = "none";
    });
    container.appendChild(div);
  });
  container.style.display = "block";
  input._stationAuto = { matches: matches, container: container, hidden: hidden, sel: 0 };
  var first = container.querySelector('.suggestion-item');
  if (first) first.classList.add('highlighted');

  if (!input._stationAutoKeydown) {
    input._stationAutoKeydown = true;
    function autoStationHighlight(i) {
      var state = input._stationAuto;
      if (!state) return;
      state.container.querySelectorAll(".suggestion-item").forEach(function(d, idx) {
        d.classList.toggle("highlighted", idx === i);
      });
      state.sel = i;
    }
    function autoStationPick(i) {
      var state = input._stationAuto;
      if (!state || i < 0 || i >= state.matches.length) return;
      input.value = state.matches[i].name;
      if (state.hidden) state.hidden.value = state.matches[i].id;
      state.container.style.display = "none";
    }
    input.addEventListener("keydown", function(e) {
      var state = input._stationAuto;
      if (!state || state.container.style.display !== "block") return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        autoStationHighlight(state.sel === -1 ? 0 : Math.min(state.sel + 1, state.matches.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        autoStationHighlight(state.sel === -1 ? 0 : Math.max(state.sel - 1, 0));
      } else if (e.key === "Enter" && state.sel >= 0) {
        e.preventDefault();
        autoStationPick(state.sel);
      }
    });
    input.addEventListener("blur", function() {
      var state = input._stationAuto;
      if (state && state.sel >= 0) autoStationPick(state.sel);
    });
  }
}

document.addEventListener("click", function (event) {
  if (event.target.closest(".autocomplete-wrap")) return;
  document.querySelectorAll(".search-suggestions").forEach(function(c) {
    c.style.display = "none";
  });
});

window.addEventListener("submit", function (event) {
  if (event.defaultPrevented) return;
  var buttons = event.target.querySelectorAll("button");
  buttons.forEach(function (button) {
    button.disabled = true;
    button.dataset.originalText = button.textContent;
    button.textContent = "Working";
  });
});

function openModal(title, formHtml) {
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-body").innerHTML = formHtml;
  document.getElementById("modal").style.display = "flex";
}

function closeModal() {
  document.getElementById("modal").style.display = "none";
}

function openModalFrom(btn, title) {
  var id = btn.getAttribute("data-modal");
  var html = document.getElementById(id).innerHTML;
  openModal(title, html);
}

var QTY_VALUES = (function() {
  var vals = [0];
  for (var v = 0.02; v <= 0.5; v = Math.round((v + 0.02) * 100) / 100) vals.push(v);
  for (var v = 0.6; v <= 1.5; v = Math.round((v + 0.1) * 100) / 100) vals.push(v);
  for (var v = 2; v <= 8; v = Math.round((v + 0.5) * 100) / 100) vals.push(v);
  return vals;
})();

function showFilter(name) {
  document.getElementById(name + "-overlay").style.display = "flex";
}

function hideFilter(name) {
  document.getElementById(name + "-overlay").style.display = "none";
}

function syncQual(event) {
  var el = event.target;
  var overlay = el.closest(".modal-overlay") || document;
  var minEl = overlay.querySelector("input[name='qual_min']");
  var maxEl = overlay.querySelector("input[name='qual_max']");
  if (!minEl || !maxEl) return;
  var minVal = parseInt(minEl.value);
  var maxVal = parseInt(maxEl.value);
  if (minVal > maxVal) { minEl.value = maxVal; minVal = maxVal; }
  var track = overlay.querySelector(".dual-slider");
  if (track) {
    track.style.setProperty("--min-pct", (minVal / 10) + "%");
    track.style.setProperty("--max-pct", (maxVal / 10) + "%");
  }
  overlay.querySelector("#qual-values").textContent = minVal + " \u2013 " + maxVal;
}

function syncQualFromStatic() {
  var overlay = document.getElementById("filter-overlay");
  if (!overlay) return;
  var minEl = overlay.querySelector("input[name='qual_min']");
  var maxEl = overlay.querySelector("input[name='qual_max']");
  if (!minEl || !maxEl) return;
  var minVal = parseInt(minEl.value);
  var maxVal = parseInt(maxEl.value);
  if (minVal > maxVal) { minEl.value = maxVal; minVal = maxVal; }
  var track = overlay.querySelector(".dual-slider");
  if (track) {
    track.style.setProperty("--min-pct", (minVal / 10) + "%");
    track.style.setProperty("--max-pct", (maxVal / 10) + "%");
  }
  overlay.querySelector("#qual-values").textContent = minVal + " \u2013 " + maxVal;
}

function updateQtyFilter(slider) {
  var idx = parseInt(slider.value);
  var scu = QTY_VALUES[idx];
  document.getElementById("qty-min-cents").value = scu.toFixed(2);
  var display = document.getElementById("qty-display");
  display.textContent = (idx === QTY_VALUES.length - 1) ? "8+ SCU" : scu.toFixed(2) + " SCU";
  var wrap = slider.closest(".qty-slider-wrap");
  if (wrap) wrap.style.setProperty("--qty-pct", (idx / (QTY_VALUES.length - 1)) * 100 + "%");
}

function initQtyFilter(scuStr) {
  var slider = document.getElementById("qty-slider");
  if (!slider) return;
  var scu = parseFloat(scuStr || 0);
  var closest = 0;
  for (var i = 0; i < QTY_VALUES.length; i++) {
    if (Math.abs(QTY_VALUES[i] - scu) < Math.abs(QTY_VALUES[closest] - scu)) closest = i;
  }
  slider.value = closest;
  var wrap = slider.closest(".qty-slider-wrap");
  if (wrap) wrap.style.setProperty("--qty-pct", (closest / (QTY_VALUES.length - 1)) * 100 + "%");
  updateQtyFilter(slider);
}
function toggleSection(el) {
  var content = el.parentElement.querySelector('.collapse-content');
  var arrow = el.querySelector('.collapse-arrow');
  if (content.style.display === 'none') {
    content.style.display = 'block';
    arrow.innerHTML = '\u25BC';
  } else {
    content.style.display = 'none';
    arrow.innerHTML = '\u25B6';
  }
}

(function() {
  var params = new URLSearchParams(window.location.search);
  var expand = params.get('expand');
  if (expand) {
    var els = document.querySelectorAll('.section-heading h2');
    for (var i = 0; i < els.length; i++) {
      if (els[i].textContent.toLowerCase().indexOf(expand.toLowerCase()) !== -1) {
        var heading = els[i].closest('.section-heading');
        if (heading) heading.click();
        break;
      }
    }
  }
})();

document.addEventListener('change', function(e) {
  var cb = e.target;
  if (cb.type !== 'checkbox') return;
  var form = cb.closest('.ext-toggle');
  if (!form) return;
  var name = form.getAttribute('data-name');
  var expand = form.getAttribute('data-expand');
  var confirmMsg = form.getAttribute('data-confirm');
  if (confirmMsg && !confirm(confirmMsg)) {
    cb.checked = !cb.checked;
    return;
  }
  var params = new URLSearchParams();
  params.set('name', name);
  fetch('/settings/toggle-extension', { method: 'POST', body: params })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.success) {
        var url = '/settings';
        if (expand) url += '?expand=' + expand;
        window.location.href = url;
      }
    });
});

function checkUpdates() {
  var status = document.getElementById('update-status');
  var results = document.getElementById('update-results');
  status.textContent = 'Checking...';
  results.innerHTML = '';
  fetch('/settings/check-updates', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var html = '';
      var hasExtUpdates = false;
      if (d.pits && d.pits.update_available) {
        html += '<div style="margin:6px 0;display:flex;align-items:center;gap:8px"><span>PITS v' + d.pits.latest + ' available (current: v' + d.pits.current + ') </span><a class="button blue" href="https://github.com/zee2ex2/SC-PITS/releases/latest" target="_blank">Download</a></div>';
      }
      for (var name in d.extensions) {
        var info = d.extensions[name];
        if (info.update_available) {
          hasExtUpdates = true;
          html += '<div style="margin:6px 0;display:flex;align-items:center;gap:8px"><span>' + name + ' v' + info.latest + ' available (current: v' + info.current + ')</span></div>';
        }
      }
      if (!html) {
        html = '<div style="color:var(--muted)">All up to date.</div>';
      } else if (hasExtUpdates) {
        html += '<div style="margin-top:12px"><button class="button green" onclick="installUpdates(\'' + encodeURIComponent(JSON.stringify(d)) + '\')">Install Extension Updates</button></div>';
      }
      results.innerHTML = html;
      status.textContent = '';
    })
    .catch(function(err) {
      status.innerHTML = '<span style="color:var(--danger)">Error checking updates</span>';
    });
}

function installUpdates(dataStr) {
  var status = document.getElementById('update-status');
  status.textContent = 'Installing...';
  var data = JSON.parse(decodeURIComponent(dataStr));
  var params = new URLSearchParams();
  params.set('data', JSON.stringify(data));
  fetch('/settings/apply-updates', { method: 'POST', body: JSON.stringify(data) })
    .then(function() {
      status.innerHTML = '<span style="color:var(--accent)">Updates applied. Restarting...</span>';
    })
    .catch(function(err) {
      status.innerHTML = '<span style="color:var(--danger)">Install failed: ' + err.message + '</span>';
    });
}