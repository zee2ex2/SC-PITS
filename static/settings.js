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

document.addEventListener('submit', function(e) {
  var form = e.target.closest('.ext-toggle');
  if (!form) return;
  e.preventDefault();
  var name = form.getAttribute('data-name');
  var expand = form.getAttribute('data-expand');
  var confirmMsg = form.getAttribute('data-confirm');
  if (confirmMsg && !confirm(confirmMsg)) return;
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
