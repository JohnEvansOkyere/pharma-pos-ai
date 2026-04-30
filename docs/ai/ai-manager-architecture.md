# AI Manager Architecture

## Intent

The AI Manager is a read-only business assistant for pharmacy managers. It gives useful operational answers without changing pharmacy data.

## Request Flow

```text
Manager asks question in Cloud Dashboard
        |
        v
Backend checks report permission and tenant scope
        |
        v
AIManagerService gathers approved reporting data
        |
        v
Disallowed requests are refused
        |
        v
Deterministic answer is composed
        |
        v
Optional external provider is called if tenant policy allows it
        |
        v
Answer returns with provider/model/fallback metadata
```

## Provider Policy

`AIProviderPolicyService` resolves provider settings.

Tenant configuration can enable:

- OpenAI
- Claude
- Groq

If external AI is disabled or credentials/model are missing, deterministic mode is used.

## Safety Controls

The provider system prompt requires:

- read-only behavior
- aggregate reporting data only
- no patient-record claims
- no stock changes
- no dispensing approval
- no pharmacy rule override
- no clinical advice
- concise operational answers

## Engineering Rule

Keep AI behind deterministic tool results. The model should explain and prioritize facts collected by backend services, not invent operational data.
