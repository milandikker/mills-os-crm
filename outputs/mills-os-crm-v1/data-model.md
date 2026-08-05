# Mills OS CRM Data Model

This is the first-pass schema for a multi-business CRM that can handle leads from website, newspaper ads, Meta, WhatsApp, and phone calls.

## Core Principle

Keep business data separated, keep messages append-only, and keep the UI fast by loading only what the user needs.

## Entities

### Business

- `id`
- `name`
- `slug`
- `theme`
- `isActive`
- `createdAt`
- `updatedAt`

### Contact

- `id`
- `businessId`
- `name`
- `email`
- `phone`
- `source`
- `tags`
- `notes`
- `lastContactAt`
- `createdAt`
- `updatedAt`

### Conversation

- `id`
- `businessId`
- `contactId`
- `channel`
- `status`
- `assignedUser`
- `lastMessageAt`
- `unreadCount`
- `createdAt`
- `updatedAt`

### Message

- `id`
- `conversationId`
- `direction`
- `channel`
- `body`
- `authorType`
- `authorName`
- `timestamp`
- `metadata`

### Lead

- `id`
- `businessId`
- `contactId`
- `conversationId`
- `stage`
- `priority`
- `value`
- `source`
- `nextFollowUpAt`
- `owner`
- `status`
- `createdAt`
- `updatedAt`

### PipelineStage

- `id`
- `businessId`
- `name`
- `order`
- `isDefault`

### CallLog

- `id`
- `businessId`
- `contactId`
- `phoneNumber`
- `direction`
- `status`
- `summary`
- `duration`
- `recordingUrl`
- `transcript`
- `createdAt`

### Task

- `id`
- `businessId`
- `leadId`
- `contactId`
- `title`
- `dueAt`
- `status`
- `assignedTo`
- `createdAt`
- `updatedAt`

### Attachment

- `id`
- `businessId`
- `contactId`
- `conversationId`
- `messageId`
- `fileName`
- `fileUrl`
- `mimeType`
- `createdAt`

### AutomationEvent

- `id`
- `businessId`
- `type`
- `payload`
- `status`
- `createdAt`
- `processedAt`

## Basic Relationships

- A `Business` has many `Contacts`, `Conversations`, `Leads`, `CallLogs`, `Tasks`, `Attachments`, and `AutomationEvents`.
- A `Contact` can have many `Conversations`, `Leads`, `CallLogs`, and `Attachments`.
- A `Conversation` contains many `Messages`.
- A `Lead` belongs to one `Contact` and one `Conversation`.

## Storage Notes

- Index `businessId`, `contactId`, `stage`, `source`, and `lastMessageAt`.
- Store messages as append-only rows.
- Keep file attachments out of the main row payload.
- Partition by business at the query layer so each workspace stays isolated.

