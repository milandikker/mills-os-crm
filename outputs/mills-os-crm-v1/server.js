import { createServer } from 'node:http';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const storePath = resolve(__dirname, 'store.json');

const defaultStore = {
  businesses: [
    { id: 'meleh-studio', name: 'Meleh Studio', slug: 'meleh-studio' },
    { id: 'millswork', name: 'Millswork', slug: 'millswork' }
  ],
  contacts: [],
  conversations: [],
  messages: [],
  leads: [],
  callLogs: [],
  tasks: [],
  attachments: [],
  automationEvents: []
};

function loadStore() {
  if (!existsSync(storePath)) return structuredClone(defaultStore);
  try {
    return JSON.parse(readFileSync(storePath, 'utf8'));
  } catch {
    return structuredClone(defaultStore);
  }
}

function saveStore(store) {
  writeFileSync(storePath, JSON.stringify(store, null, 2));
}

function json(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data, null, 2));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', chunk => { raw += chunk; });
    req.on('end', () => {
      if (!raw) return resolve({});
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(new Error('Invalid JSON body'));
      }
    });
    req.on('error', reject);
  });
}

function nowIso() {
  return new Date().toISOString();
}

function classifyIntent(payload) {
  const text = `${payload.intent ?? ''} ${payload.message ?? ''} ${payload.details ?? ''}`.toLowerCase();
  if (text.includes('quote') || text.includes('price') || text.includes('pricing') || text.includes('custom') || text.includes('commission')) {
    return 'custom_quote';
  }
  if (text.includes('call') || text.includes('phone') || text.includes('missed')) {
    return 'phone_followup';
  }
  if (text.includes('ship') || text.includes('where') || text.includes('when') || text.includes('size') || text.includes('finish')) {
    return 'product_inquiry';
  }
  return 'general_inquiry';
}

function buildAiResponse(payload, mode) {
  const intent = classifyIntent(payload);
  const name = payload.contactName ?? payload.name ?? 'there';

  if (mode === 'summarize') {
    return {
      summary: `Lead summary for ${name}: intent ${intent.replace('_', ' ')}, awaiting the next qualifying detail, and ready for either AI follow-up or human handoff.`,
      stageSuggestion: intent === 'custom_quote' ? 'Custom Quote Requested' : 'Waiting on Info',
      handoff: intent === 'custom_quote' || intent === 'phone_followup'
    };
  }

  const followUp = {
    custom_quote: 'Could you share the preferred size, finish, deadline, and whether you have a reference photo?',
    product_inquiry: 'Could you tell me which size or variation you are considering so I can point you to the best option?',
    phone_followup: 'I see you called in. What is the best time to call you back, and what should we prepare before the callback?',
    general_inquiry: 'Could you share a little more detail so I can point you in the right direction?'
  };

  return {
    draft: `Shalom ${name}, thank you for reaching out. ${followUp[intent]} We’ll make sure the next step is easy and clear.`,
    intent,
    qualified: intent !== 'general_inquiry',
    stageSuggestion: intent === 'custom_quote' ? 'Custom Quote Requested' : intent === 'product_inquiry' ? 'Product Inquiry' : 'New Lead',
    handoff: intent === 'custom_quote' || intent === 'phone_followup'
  };
}

function recordAutomationEvent(store, businessId, type, payload) {
  store.automationEvents.push({
    id: `automation_${crypto.randomUUID()}`,
    businessId,
    type,
    payload,
    status: 'queued',
    createdAt: nowIso(),
    processedAt: ''
  });
}

function getOrCreateContact(store, payload) {
  const match = store.contacts.find(contact => {
    return (
      (payload.email && contact.email === payload.email) ||
      (payload.phone && contact.phone === payload.phone)
    );
  });

  if (match) {
    Object.assign(match, {
      name: payload.name ?? match.name,
      email: payload.email ?? match.email,
      phone: payload.phone ?? match.phone,
      source: payload.source ?? match.source,
      notes: payload.notes ?? match.notes,
      lastContactAt: nowIso(),
      updatedAt: nowIso()
    });
    return match;
  }

  const contact = {
    id: `contact_${crypto.randomUUID()}`,
    businessId: payload.businessId,
    name: payload.name ?? 'Unknown',
    email: payload.email ?? '',
    phone: payload.phone ?? '',
    source: payload.source ?? 'website',
    tags: payload.tags ?? [],
    notes: payload.notes ?? '',
    lastContactAt: nowIso(),
    createdAt: nowIso(),
    updatedAt: nowIso()
  };

  store.contacts.push(contact);
  return contact;
}

function ensureConversation(store, contact, payload) {
  let conversation = store.conversations.find(item =>
    item.businessId === payload.businessId &&
    item.contactId === contact.id &&
    item.channel === payload.channel
  );

  if (!conversation) {
    conversation = {
      id: `conversation_${crypto.randomUUID()}`,
      businessId: payload.businessId,
      contactId: contact.id,
      channel: payload.channel ?? 'website',
      status: 'open',
      assignedUser: payload.assignedUser ?? '',
      lastMessageAt: nowIso(),
      unreadCount: 1,
      createdAt: nowIso(),
      updatedAt: nowIso()
    };
    store.conversations.push(conversation);
    return conversation;
  }

  conversation.lastMessageAt = nowIso();
  conversation.unreadCount = (conversation.unreadCount ?? 0) + 1;
  conversation.updatedAt = nowIso();
  return conversation;
}

function createLead(store, contact, conversation, payload) {
  let lead = store.leads.find(item =>
    item.businessId === payload.businessId &&
    item.contactId === contact.id
  );

  if (!lead) {
    lead = {
      id: `lead_${crypto.randomUUID()}`,
      businessId: payload.businessId,
      contactId: contact.id,
      conversationId: conversation.id,
      stage: payload.stage ?? 'New Lead',
      priority: payload.priority ?? 'Normal',
      value: payload.value ?? 0,
      source: payload.source ?? 'website',
      nextFollowUpAt: payload.nextFollowUpAt ?? '',
      owner: payload.owner ?? '',
      status: 'open',
      createdAt: nowIso(),
      updatedAt: nowIso()
    };
    store.leads.push(lead);
    return lead;
  }

  Object.assign(lead, {
    conversationId: conversation.id,
    stage: payload.stage ?? lead.stage,
    priority: payload.priority ?? lead.priority,
    source: payload.source ?? lead.source,
    nextFollowUpAt: payload.nextFollowUpAt ?? lead.nextFollowUpAt,
    owner: payload.owner ?? lead.owner,
    updatedAt: nowIso()
  });
  return lead;
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`);
  const store = loadStore();

  if (req.method === 'GET' && url.pathname === '/health') {
    return json(res, 200, { ok: true, service: 'mills-os-crm-v1' });
  }

  if (req.method === 'GET' && url.pathname === '/businesses') {
    return json(res, 200, store.businesses);
  }

  if (req.method === 'GET' && url.pathname === '/conversations') {
    const businessId = url.searchParams.get('businessId');
    const items = businessId
      ? store.conversations.filter(item => item.businessId === businessId)
      : store.conversations;
    return json(res, 200, items);
  }

  if (req.method === 'GET' && url.pathname === '/leads') {
    const businessId = url.searchParams.get('businessId');
    const items = businessId
      ? store.leads.filter(item => item.businessId === businessId)
      : store.leads;
    return json(res, 200, items);
  }

  if (req.method === 'GET' && url.pathname === '/calls') {
    const businessId = url.searchParams.get('businessId');
    const items = businessId
      ? store.callLogs.filter(item => item.businessId === businessId)
      : store.callLogs;
    return json(res, 200, items);
  }

  if (req.method === 'POST' && url.pathname === '/intake/website') {
    const payload = await readBody(req);
    const contact = getOrCreateContact(store, payload);
    const conversation = ensureConversation(store, contact, { ...payload, channel: 'website' });
    const lead = createLead(store, contact, conversation, { ...payload, source: 'website' });
    store.messages.push({
      id: `message_${crypto.randomUUID()}`,
      conversationId: conversation.id,
      direction: 'inbound',
      channel: 'website',
      body: payload.message ?? payload.details ?? '',
      authorType: 'customer',
      authorName: contact.name,
      timestamp: nowIso(),
      metadata: payload.metadata ?? {}
    });
    recordAutomationEvent(store, payload.businessId, 'website_intake', { contactId: contact.id, conversationId: conversation.id, leadId: lead.id });
    saveStore(store);
    return json(res, 201, { contact, conversation, lead });
  }

  if (req.method === 'POST' && url.pathname === '/intake/chat') {
    const payload = await readBody(req);
    const contact = getOrCreateContact(store, payload);
    const conversation = ensureConversation(store, contact, { ...payload, channel: 'website-chat' });
    const lead = createLead(store, contact, conversation, { ...payload, source: 'chat' });
    store.messages.push({
      id: `message_${crypto.randomUUID()}`,
      conversationId: conversation.id,
      direction: 'inbound',
      channel: 'website-chat',
      body: payload.message ?? '',
      authorType: 'customer',
      authorName: contact.name,
      timestamp: nowIso(),
      metadata: payload.metadata ?? {}
    });
    recordAutomationEvent(store, payload.businessId, 'chat_intake', { contactId: contact.id, conversationId: conversation.id, leadId: lead.id });
    saveStore(store);
    return json(res, 201, { contact, conversation, lead });
  }

  if (req.method === 'POST' && url.pathname === '/intake/meta') {
    const payload = await readBody(req);
    const contact = getOrCreateContact(store, payload);
    const conversation = ensureConversation(store, contact, { ...payload, channel: payload.channel ?? 'meta' });
    const lead = createLead(store, contact, conversation, { ...payload, source: 'meta' });
    store.messages.push({
      id: `message_${crypto.randomUUID()}`,
      conversationId: conversation.id,
      direction: 'inbound',
      channel: payload.channel ?? 'meta',
      body: payload.message ?? '',
      authorType: 'customer',
      authorName: contact.name,
      timestamp: nowIso(),
      metadata: payload.metadata ?? {}
    });
    recordAutomationEvent(store, payload.businessId, 'meta_intake', { contactId: contact.id, conversationId: conversation.id, leadId: lead.id, channel: payload.channel ?? 'meta' });
    saveStore(store);
    return json(res, 201, { contact, conversation, lead });
  }

  if (req.method === 'POST' && url.pathname === '/intake/whatsapp') {
    const payload = await readBody(req);
    const contact = getOrCreateContact(store, payload);
    const conversation = ensureConversation(store, contact, { ...payload, channel: 'whatsapp' });
    const lead = createLead(store, contact, conversation, { ...payload, source: 'whatsapp' });
    store.messages.push({
      id: `message_${crypto.randomUUID()}`,
      conversationId: conversation.id,
      direction: 'inbound',
      channel: 'whatsapp',
      body: payload.message ?? '',
      authorType: 'customer',
      authorName: contact.name,
      timestamp: nowIso(),
      metadata: payload.metadata ?? {}
    });
    recordAutomationEvent(store, payload.businessId, 'whatsapp_intake', { contactId: contact.id, conversationId: conversation.id, leadId: lead.id });
    saveStore(store);
    return json(res, 201, { contact, conversation, lead });
  }

  if (req.method === 'POST' && url.pathname === '/intake/calls') {
    const payload = await readBody(req);
    const contact = getOrCreateContact(store, payload);
    const entry = {
      id: `call_${crypto.randomUUID()}`,
      businessId: payload.businessId,
      contactId: contact.id,
      phoneNumber: payload.phoneNumber ?? contact.phone ?? '',
      direction: payload.direction ?? 'inbound',
      status: payload.status ?? 'missed',
      summary: payload.summary ?? '',
      duration: payload.duration ?? 0,
      recordingUrl: payload.recordingUrl ?? '',
      transcript: payload.transcript ?? '',
      createdAt: nowIso()
    };
    store.callLogs.push(entry);
    recordAutomationEvent(store, payload.businessId, 'call_intake', { contactId: contact.id, callId: entry.id, status: entry.status });
    saveStore(store);
    return json(res, 201, { contact, callLog: entry });
  }

  if (req.method === 'PATCH' && url.pathname.startsWith('/leads/')) {
    const leadId = url.pathname.split('/').pop();
    const payload = await readBody(req);
    const lead = store.leads.find(item => item.id === leadId);
    if (!lead) return json(res, 404, { error: 'Lead not found' });
    Object.assign(lead, payload, { updatedAt: nowIso() });
    saveStore(store);
    return json(res, 200, lead);
  }

  if (req.method === 'POST' && url.pathname === '/messages') {
    const payload = await readBody(req);
    const message = {
      id: `message_${crypto.randomUUID()}`,
      conversationId: payload.conversationId,
      direction: payload.direction ?? 'outbound',
      channel: payload.channel ?? 'manual',
      body: payload.body ?? '',
      authorType: payload.authorType ?? 'user',
      authorName: payload.authorName ?? 'Mills OS',
      timestamp: nowIso(),
      metadata: payload.metadata ?? {}
    };
    store.messages.push(message);
    saveStore(store);
    return json(res, 201, message);
  }

  if (req.method === 'POST' && url.pathname === '/tasks') {
    const payload = await readBody(req);
    const task = {
      id: `task_${crypto.randomUUID()}`,
      businessId: payload.businessId,
      leadId: payload.leadId ?? '',
      contactId: payload.contactId ?? '',
      title: payload.title ?? 'Follow up',
      dueAt: payload.dueAt ?? '',
      status: payload.status ?? 'open',
      assignedTo: payload.assignedTo ?? '',
      createdAt: nowIso(),
      updatedAt: nowIso()
    };
    store.tasks.push(task);
    recordAutomationEvent(store, payload.businessId, 'task_created', { taskId: task.id, leadId: task.leadId, contactId: task.contactId });
    saveStore(store);
    return json(res, 201, task);
  }

  if (req.method === 'POST' && url.pathname === '/ai/draft') {
    const payload = await readBody(req);
    return json(res, 200, buildAiResponse(payload, 'draft'));
  }

  if (req.method === 'POST' && url.pathname === '/ai/summarize') {
    const payload = await readBody(req);
    return json(res, 200, buildAiResponse(payload, 'summarize'));
  }

  if (req.method === 'POST' && url.pathname === '/ai/decide') {
    const payload = await readBody(req);
    const result = buildAiResponse(payload, 'draft');
    const businessId = payload.businessId ?? '';
    if (businessId) {
      recordAutomationEvent(store, businessId, 'ai_decision', result);
      saveStore(store);
    }
    return json(res, 200, result);
  }

  if (req.method === 'GET' && url.pathname === '/messages') {
    const conversationId = url.searchParams.get('conversationId');
    const items = conversationId
      ? store.messages.filter(item => item.conversationId === conversationId)
      : store.messages;
    return json(res, 200, items);
  }

  return json(res, 404, { error: 'Not found', path: url.pathname });
});

const port = Number(process.env.PORT ?? 8787);
server.listen(port, () => {
  console.log(`Mills OS CRM V1 listening on http://localhost:${port}`);
});
