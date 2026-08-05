const businessSwitcher = document.getElementById('businessSwitcher');
const activeBusinessName = document.getElementById('activeBusinessName');
const detailBusiness = document.getElementById('detailBusiness');
const detailStage = document.getElementById('detailStage');
const contactName = document.getElementById('contactName');
const contactSummary = document.getElementById('contactSummary');
const detailName = document.getElementById('detailName');
const cards = Array.from(document.querySelectorAll('.conversation-card'));
const navItems = Array.from(document.querySelectorAll('.nav-item'));
const panels = Array.from(document.querySelectorAll('[data-panel]'));

const conversations = {
  rachel: {
    name: 'Rachel Ben-Ami',
    summary: 'Assigned to Miriam Cohen · High priority · Quote not yet sent',
    stage: 'Custom Quote Requested'
  },
  david: {
    name: 'David Cohen',
    summary: 'Website lead · Product inquiry · Awaiting reply',
    stage: 'Product Inquiry'
  },
  sarah: {
    name: 'Sarah Levi',
    summary: 'Meta lead · Shipping question · Waiting on info',
    stage: 'Waiting on Info'
  },
  yael: {
    name: 'Yael Fridman',
    summary: 'Missed call · Follow-up needed · High priority',
    stage: 'Missed Call'
  }
};

const businessStates = {
  'Meleh Studio': {
    label: 'Meleh Studio',
    stage: 'Custom Quote Requested',
    summary: 'Assigned to Miriam Cohen · High priority · Quote not yet sent'
  },
  Millswork: {
    label: 'Millswork',
    stage: 'New Lead',
    summary: 'Assigned to team · General inquiries · Active service leads'
  }
};

function setActiveConversation(id) {
  cards.forEach((card) => card.classList.toggle('selected', card.dataset.contact === id));
  const data = conversations[id];
  if (!data) return;
  contactName.textContent = data.name;
  detailName.textContent = data.name;
  detailStage.textContent = data.stage;
  contactSummary.textContent = data.summary;
}

function setView(viewName) {
  navItems.forEach((item) => item.classList.toggle('active', item.dataset.view === viewName));
  panels.forEach((panel) => panel.classList.toggle('active', panel.dataset.panel === viewName));
}

businessSwitcher.addEventListener('change', () => {
  const selected = businessStates[businessSwitcher.value];
  activeBusinessName.textContent = selected.label;
  detailBusiness.textContent = selected.label;
  detailStage.textContent = selected.stage;
  contactSummary.textContent = selected.summary;
});

cards.forEach((card) => {
  card.addEventListener('click', () => setActiveConversation(card.dataset.contact));
});

navItems.forEach((item) => {
  item.addEventListener('click', () => setView(item.dataset.view));
});

setActiveConversation('rachel');
setView('inbox');
