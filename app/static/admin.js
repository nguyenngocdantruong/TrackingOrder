(() => {
  const form = document.querySelector('#settings');
  if (!form) return;
  const sections = [...form.querySelectorAll('section')];
  const links = [...document.querySelectorAll('nav [data-section]')];
  const status = document.querySelector('#save-state');
  const initial = new Map([...form.elements].filter(e => e.name).map(e => [e, e.type === 'checkbox' ? e.checked : e.value]));
  let dirty = false;
  function select(id) {
    const selected = sections.find(s => s.id === id) || sections[0];
    sections.forEach(s => { s.hidden = s !== selected; });
    links.forEach(a => {
      if (a.dataset.section === selected.id) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
  }
  document.documentElement.classList.add('js-ready');
  select(location.hash.slice(1));
  links.forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    history.replaceState(null, '', a.hash);
    select(a.dataset.section);
  }));
  window.addEventListener('hashchange', () => select(location.hash.slice(1)));
  form.addEventListener('input', () => {
    const changed = [...initial].filter(([e, value]) => (e.type === 'checkbox' ? e.checked : e.value) !== value);
    dirty = changed.length > 0;
    status.textContent = dirty ? `${changed.length} thay đổi chưa lưu` : 'Chưa có thay đổi';
    links.forEach(a => a.toggleAttribute('data-dirty', changed.some(([e]) => e.closest('section')?.id === a.dataset.section)));
    form.querySelectorAll('.switch-control').forEach(c => { c.querySelector('.switch-state').textContent = c.querySelector('input').checked ? 'Bật' : 'Tắt'; });
  });
  form.addEventListener('invalid', e => {
    const section = e.target.closest('section');
    if (section) select(section.id);
  }, true);
  form.addEventListener('submit', () => {
    dirty = false;
    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    button.textContent = 'Đang lưu…';
    status.textContent = 'Đang áp dụng cấu hình';
  });
  window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
})();
