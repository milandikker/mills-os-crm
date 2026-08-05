# Mills OS CRM API Plan

This is the first pass on the internal API surface for the CRM.

## Intake Endpoints

### `POST /intake/website`

- Receives website form submissions.
- Creates or updates contact.
- Creates lead and conversation records.

### `POST /intake/chat`

- Receives website chat submissions.
- Appends message to conversation.
- Triggers AI draft if enabled.

### `POST /intake/meta`

- Receives Facebook and Instagram message events.
- Routes into the correct business and conversation.

### `POST /intake/whatsapp`

- Receives WhatsApp webhook events.
- Saves the conversation and message metadata.

### `POST /intake/calls`

- Receives phone call events.
- Creates a call log entry.
- Links the call to a contact or creates a new one.

## Read APIs

### `GET /businesses`

- Returns businesses available to the user.

### `GET /conversations?businessId=`

- Returns conversation list for a workspace.

### `GET /conversations/:id`

- Returns full thread and lead context.

### `GET /leads?businessId=`

- Returns pipeline-ready leads.

### `GET /calls?businessId=`

- Returns recent call log entries.

## Write APIs

### `PATCH /leads/:id`

- Update stage.
- Update priority.
- Update owner.
- Update follow-up.

### `POST /messages`

- Send a manual reply.
- Save the outgoing message.

### `POST /ai/draft`

- Generate a draft reply.
- Use the current thread context and lead data.

### `POST /ai/summarize`

- Summarize the conversation and the lead context.

### `POST /tasks`

- Create a follow-up task.

## Workflow Notes

- Every intake request resolves `businessId` first.
- Every write operation must carry a workspace context.
- AI actions should be asynchronous when possible.
- Manual replies should always be allowed even when AI is enabled.

