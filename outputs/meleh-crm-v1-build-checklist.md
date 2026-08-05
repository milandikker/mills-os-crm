# Meleh CRM V1 Build Checklist

This is the first working version of the custom CRM. The goal is not to build a giant platform. The goal is to ship a simple system that actually works every day, handles multiple businesses later, and gives AI a real role from the start.

## V1 Goal

- Capture leads from website, newspaper ads, Facebook, Instagram, WhatsApp, and phone calls.
- Let the user reply manually or with AI assistance.
- Keep a clear pipeline for lead status.
- Support multiple businesses inside one platform.
- Use the Mills OS visual language: dark shell, orange glow, command-center feel.

## Must-Have Screens

### 1. Inbox

- Conversation list on the left.
- Active conversation in the center.
- Lead details on the right.
- Channel badges for website, Facebook, Instagram, WhatsApp, and phone.
- Unread counts and priority indicators.

### 2. Lead Detail

- Name.
- Phone.
- Email.
- Source.
- Business/workspace.
- Status.
- Priority.
- Tags.
- Last message.
- Next follow-up.
- Notes.
- Attachments.

### 3. Pipeline

- New lead.
- Product inquiry.
- Custom quote requested.
- Waiting on info.
- Quote sent.
- Won.
- Lost.

### 4. AI Hub

- Draft reply button.
- Summarize thread button.
- Qualify lead button.
- Suggest next step button.
- Human handoff indicator.

### 5. Business Switcher

- Switch between businesses.
- Show active workspace.
- Keep brand data separated.

### 6. Call Log

- Incoming call record.
- Missed call record.
- Call note.
- Optional transcript later.

## Must-Have Behaviors

### Lead Capture

- Create a new contact or update an existing one.
- Attach source and business automatically.
- Route the lead into the correct inbox and pipeline.

### AI Behavior

- Greet the customer.
- Classify the intent.
- Ask simple qualifying questions.
- Draft helpful replies.
- Escalate to human when needed.

### Human Workflow

- Reply directly.
- Add notes.
- Change stage.
- Set follow-up.
- Mark won or lost.

### Search and Filtering

- Search by name.
- Search by phone.
- Search by email.
- Search by business.
- Search by source.
- Search by stage.
- Filter by unread, priority, and assigned owner.

## Data Model

- `Business`
- `Contact`
- `Conversation`
- `Message`
- `Lead`
- `PipelineStage`
- `CallLog`
- `Task`
- `Attachment`
- `AutomationEvent`

## Build Order

### Phase 1: Core Plumbing

- Set up the database schema.
- Create the webhook intake endpoint.
- Save leads from the website.
- Save leads from chat.
- Save message metadata.

### Phase 2: Inbox UI

- Build the conversation list.
- Build the message thread view.
- Build the lead detail panel.
- Build unread/priority states.

### Phase 3: Pipeline UI

- Build the simple board.
- Allow stage changes.
- Sync stage with the lead record.

### Phase 4: AI Layer

- Generate draft replies.
- Summarize conversations.
- Suggest qualification questions.
- Flag human handoff.

### Phase 5: Channels

- Website chat.
- Website form.
- Meta messaging.
- WhatsApp later.
- Call logging.

### Phase 6: Multi-Business Support

- Add business switcher.
- Partition data by business.
- Keep UI neutral and brandable.

## Not in V1

- Billing.
- Complex analytics.
- Deep permission management.
- Advanced campaign builders.
- Fancy reporting dashboards.
- Overbuilt automation editor.

## Definition of Done

- Leads from the main channels land in the system.
- Conversations are visible in one inbox.
- AI can assist with replies.
- The pipeline works.
- Calls are logged.
- Multiple businesses can be separated cleanly.
- The UI feels like a real tool the user wants to open every day.

