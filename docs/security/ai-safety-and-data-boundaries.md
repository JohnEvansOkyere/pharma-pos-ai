# AI Safety And Data Boundaries

## AI Purpose

AI is a manager assistant and reporting helper. It should make the product feel intelligent by summarizing risks, explaining performance, and preparing action plans.

AI must not replace deterministic pharmacy controls.

## Allowed AI Work

Allowed:

- summarize sales and branch performance
- explain low-stock and expiry risks
- highlight sync/reconciliation issues
- prepare weekly manager reports
- recommend operational follow-up tasks
- answer questions using approved aggregate reporting data
- draft email/Telegram manager report content

## Disallowed AI Work

Disallowed:

- clinical advice
- dispensing approval
- prescription override
- controlled-drug guidance
- stock mutation
- user or permission mutation
- silent business-rule override
- direct database changes

The AI manager service returns a refusal for disallowed request categories.

## Data Sources

AI uses approved cloud reporting data:

- sales facts
- inventory movement facts
- sync health
- product snapshots
- batch snapshots
- reconciliation output

AI should not claim access to data it was not given.

## Providers

Supported provider modes:

- deterministic
- OpenAI
- Claude/Anthropic
- Groq

Tenant policy controls whether external AI is enabled, which providers are allowed, and which model is preferred. If external provider configuration is missing or fails, the system falls back to deterministic output.

## Weekly Reports

Weekly manager reports are generated for the coming action week while referencing the just-ended performance period.

Default schedule:

- Sunday
- 7:00 PM
- configured timezone, currently defaulting to Africa/Accra

Reports include:

- performance period
- action period
- executive summary
- stock risk priorities
- sales and branch performance
- inventory movements
- sync and reconciliation quality
- safety notes
- provider/model/fallback metadata

## Delivery

Supported delivery channels:

- email
- Telegram

WhatsApp is intentionally not implemented at this phase due to setup complexity.

Delivery records are persisted and retryable when configured.
