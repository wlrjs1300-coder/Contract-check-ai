# PR-6 AI provider policy review and final decision

Status: Final
Review status: Independent review completed
GitHub status: PR #25 merged
Provider selection: Not selected
External AI use approval: Not granted
v0.2.1 completion: Completed as technical validation phase

## 1. Document purpose

This report records the PR-6 official policy review for ContractCheck AI v0.2.1.

The review checks whether an external AI API can be considered for the MVP after the local PR-2 to PR-5 spike results:

- PR-2 clause splitting validation
- PR-3 personal data detection and masking validation
- PR-4 masking usefulness validation
- PR-5 output safety validation

This report is the final technical decision document after independent review and PR #25 merge. It is a technical decision aid. It is not legal advice, privacy compliance certification, operational approval, production approval, or provider selection.

v0.2.1 is complete as a technical validation phase, but this does not approve external AI use or implementation. Actual provider selection, endpoint and model choice, contractual conditions, retention controls, and operational approval require separate later confirmation.

## 2. Scope

### Reviewed providers

| Provider | Scope |
|---|---|
| OpenAI API | Official API and business/developer policy documents |
| Anthropic API | Official Claude API and commercial policy documents |
| Google Gemini API | Official Gemini API developer and paid/unpaid service policy documents |

### Excluded from direct comparison

- Azure OpenAI
- AWS Bedrock
- Google Vertex AI
- Local models
- Self-hosted open source models
- Consumer ChatGPT, Claude, and Gemini apps

## 3. Official source table

Checked date: 2026-07-14

If a reviewed page did not display a last updated or effective date, this report records that fact instead of inferring a date.

| Provider | Document title | Official URL | Checked date | Last updated / Effective date | Applicable product / API scope | Supported decision items | Uncertainty / Follow-up required |
|---|---|---|---|---|---|---|---|
| OpenAI | Data controls in the OpenAI platform | https://developers.openai.com/api/docs/guides/your-data | 2026-07-14 | Not displayed on reviewed page | OpenAI API Platform | API training use, abuse monitoring retention, application state retention, Zero Data Retention, endpoint limits | Confirm exact endpoint, model, `store` behavior, ZDR eligibility, and enabled organization controls before implementation |
| OpenAI | Enterprise privacy at OpenAI | https://openai.com/enterprise-privacy/ | 2026-07-14 | Not displayed on reviewed page | OpenAI business/developer services | business data ownership, human access, security controls, API privacy FAQ | Confirm whether the actual project account and terms qualify for the described controls |
| OpenAI | OpenAI Services Agreement | https://openai.com/policies/services-agreement/ | 2026-07-14 | Effective date not displayed on reviewed page | OpenAI business/developer services | contractual scope and customer content responsibilities | Confirm applicable contracting entity, DPA, and account terms before real use |
| OpenAI | Structured model outputs | https://developers.openai.com/api/docs/guides/structured-outputs | 2026-07-14 | Not displayed on reviewed page | OpenAI API Platform | JSON Schema / structured output fit | Confirm selected model support and schema limits |
| OpenAI | Models | https://developers.openai.com/api/docs/models | 2026-07-14 | Not displayed on reviewed page | OpenAI API Platform | model capability, context, price snapshot | Re-check selected model availability and pricing before implementation |
| OpenAI | Rate limits | https://developers.openai.com/api/docs/guides/rate-limits | 2026-07-14 | Not displayed on reviewed page | OpenAI API Platform | rate and usage limit behavior | Confirm project and organization limits before implementation |
| Anthropic | Is my data used for model training? | https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training | 2026-07-14 | Not displayed on reviewed page | Anthropic API commercial products | commercial/API training use | Confirm selected product path remains commercial/API and does not rely on consumer policy |
| Anthropic | How long do you store my organization's data? | https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data | 2026-07-14 | Not displayed on reviewed page | Anthropic API commercial products | API retention, Files API exception, ZDR, policy violation retention | Confirm endpoint, Files API usage, and separate retention agreement status before implementation |
| Anthropic | Commercial Terms of Service | https://www.anthropic.com/legal/commercial-terms | 2026-07-14 | Effective date not displayed on reviewed page | Anthropic API commercial products | API terms, content ownership, output limitations, confidentiality | Confirm applicable commercial terms and DPA before real use |
| Anthropic | Structured outputs | https://platform.claude.com/docs/en/build-with-claude/structured-outputs | 2026-07-14 | Not displayed on reviewed page | Anthropic API commercial products | JSON / strict tool schema support | Confirm selected model and tool schema limits |
| Anthropic | Models overview | https://platform.claude.com/docs/en/about-claude/models/overview | 2026-07-14 | Not displayed on reviewed page | Anthropic API commercial products | model capability, context, price snapshot | Re-check selected model availability and pricing before implementation |
| Anthropic | Rate limits | https://platform.claude.com/docs/en/api/rate-limits | 2026-07-14 | Not displayed on reviewed page | Anthropic API commercial products | spend and rate limits | Confirm workspace, tier, and model-specific limits |
| Anthropic | Pricing | https://claude.com/pricing | 2026-07-14 | Not displayed on reviewed page | Anthropic API commercial products | pricing and account controls | Confirm API billing path and enterprise controls before implementation |
| Google Gemini API | Gemini API Additional Terms of Service | https://ai.google.dev/gemini-api/terms | 2026-07-14 | Effective date not displayed on reviewed page | Gemini Developer API Unpaid Services and Gemini Developer API Paid Services | paid/unpaid data use, human review, sensitive information warning, professional advice warning | Confirm paid service terms, DPA path, and whether the chosen model/tier is paid-only before implementation |
| Google Gemini API | Gemini Developer API pricing | https://ai.google.dev/gemini-api/docs/pricing | 2026-07-14 | Not displayed on reviewed page | Gemini Developer API Free Tier and Paid Tier | free/paid data use distinction, "Used to improve our products" tier column, model/tier pricing | Re-check selected model and processing mode because free/paid availability varies by model and mode |
| Google Gemini API | Rate limits | https://ai.google.dev/gemini-api/docs/rate-limits | 2026-07-14 | Not displayed on reviewed page | Gemini Developer API | project limits, paid/free quota behavior | Confirm selected project limits and budget controls |
| Google Gemini API | Available regions | https://ai.google.dev/gemini-api/docs/available-regions | 2026-07-14 | Not displayed on reviewed page | Gemini Developer API | supported regions | Confirm service availability for deployment region and user disclosure |
| Google Gemini API | Structured outputs | https://ai.google.dev/gemini-api/docs/structured-output | 2026-07-14 | Not displayed on reviewed page | Gemini Developer API | JSON Schema output support | Confirm selected model support and schema limits |
| Google Gemini API | Models | https://ai.google.dev/gemini-api/docs/models | 2026-07-14 | Not displayed on reviewed page | Gemini Developer API | model availability and capability | Re-check selected model and tier before implementation |
| Google | Business data responsibility and compliance | https://business.safety.google/compliance/ | 2026-07-14 | Not displayed on reviewed page | Google business security and compliance background | security and compliance background only | Do not treat this as Gemini API-specific data retention approval |

## 4. Policy comparison by required item

### 4.1 Training use of input data

| Provider | Finding | Grade |
|---|---|---|
| OpenAI API | Official API data controls state that API data is not used to train or improve models by default unless explicitly opted in. | PASS |
| Anthropic API | Commercial/API documentation states inputs and outputs are not used for model training by default. Feedback or explicit permission can be used. | PASS |
| Google Gemini API | Free/unpaid services may use submitted content and generated responses to improve products and may involve human review. The reviewed Gemini API terms also warn users not to submit sensitive, confidential, or personal information to Unpaid Services. Paid Gemini API quota states prompts and responses are not used to improve products. | CONDITIONAL |

Gemini API Unpaid Services are BLOCKED for ContractCheck AI contract analysis. Google Gemini API must be treated as paid-quota-only for any later review, but paid quota is not automatically approved.

### 4.2 Data retention

| Provider | Finding | Grade |
|---|---|---|
| OpenAI API | Default abuse monitoring retention can be up to 30 days for many endpoints. Responses API can also have application state retention: `store=true` can retain response data for at least 30 days, ZDR-enabled organizations treat store requests as false regardless of the request value, and background mode can retain response data for about 10 minutes for polling. ZDR or modified abuse monitoring may be available only for approved eligible use cases and endpoints. | CONDITIONAL |
| Anthropic API | API inputs and outputs are automatically deleted within 30 days by default. Exceptions include Files API or other customer-controlled longer-retention services, separate zero data retention agreements, usage policy enforcement, legal obligations, or other separate agreement terms. | CONDITIONAL |
| Google Gemini API | Paid services log prompts and responses for a limited period for abuse prevention, safety, security, and legal/regulatory purposes. The exact operational period for general paid Gemini API logging is not stated in the reviewed terms page. Grounding features have specific 30-day storage language. Free/unpaid quota remains excluded because unpaid input/output may be used for improvement and reviewed by humans. | REVIEW |

For all providers, ContractCheck AI must assume that masked input may be retained temporarily unless a verified and applicable reduced-retention arrangement is active.

### 4.3 Human access possibility

| Provider | Finding | Grade |
|---|---|---|
| OpenAI API | Stored API business data may be accessed by authorized employees for engineering support, abuse investigation, legal compliance, and specialized contractors for abuse/misuse review under confidentiality obligations. | CONDITIONAL |
| Anthropic API | Commercial terms protect customer confidential information, but policy violation and safety processes can require retention and review. Covered model requirements require additional confirmation for the exact model selected. | REVIEW |
| Google Gemini API | Unpaid services explicitly allow human reviewers to read and process input/output. Paid services are processed under DPA terms, but abuse/safety logging still applies. | CONDITIONAL |

Human review possibility is not fully eliminated by any provider based on reviewed public documents.

### 4.4 Region and international transfer

| Provider | Finding | Grade |
|---|---|---|
| OpenAI API | Data residency controls exist for eligible customers, regions, endpoints, models, and configurations. System data may be processed outside the selected region. | CONDITIONAL |
| Anthropic API | Commercial terms distinguish contracting entity by region and incorporate a DPA. Specific inference/data residency requirements need separate confirmation for the selected product path. | REVIEW |
| Google Gemini API | Gemini API is region-restricted by availability. Paid services state data may be stored transiently or cached in any country where Google or its agents maintain facilities. | REVIEW |

MVP design must not promise domestic-only processing or complete region control.

### 4.5 Deletion and retention end

| Provider | Finding | Grade |
|---|---|---|
| OpenAI API | API data retention depends on endpoint and data controls. Responses API application state behavior depends on `store`, ZDR status, and background mode. Some persistent objects are retained until deleted. ZDR does not cover every endpoint or feature, and the 30-day retention statement must not be applied uniformly to every OpenAI API endpoint. | CONDITIONAL |
| Anthropic API | API inputs/outputs are deleted within 30 days by default except listed exceptions. Files API or other customer-controlled longer-retention services must be distinguished from ordinary API requests. Feedback, policy violations, law, and separate agreement terms may extend retention. | CONDITIONAL |
| Google Gemini API | Paid services retain logs for policy/security/legal purposes; feature-specific terms can impose separate retention. General deletion mechanics for paid Gemini API prompts require further confirmation. | REVIEW |

ContractCheck AI must not tell users that external provider deletion is immediate or perfect.

### 4.6 Security and compliance

| Provider | Finding | Grade |
|---|---|---|
| OpenAI API | OpenAI states SOC 2 Type 2 for API Platform, encryption at rest and in transit, access controls, and DPA availability. | PASS |
| Anthropic API | Anthropic provides commercial terms, DPA reference, trust center, enterprise controls, and pricing pages noting admin controls and custom retention controls for enterprise paths. | CONDITIONAL |
| Google Gemini API | Google publishes business compliance information including third-party audits and certifications for Google Cloud/Workspace contexts; Gemini API paid services are tied to Google Cloud billing and data processor terms. | CONDITIONAL |

Public compliance evidence is useful but does not by itself approve ContractCheck AI for real personal data or real contract processing.

### 4.7 API feature fit

| Provider | Finding | Grade |
|---|---|---|
| OpenAI API | Structured Outputs support JSON Schema; current model catalog includes long context models and text/image input. | PASS |
| Anthropic API | Structured outputs support JSON format and strict tool use; current Claude models include long context and text/image input. | PASS |
| Google Gemini API | Gemini API supports structured output using JSON Schema. Current model capabilities and supported input/output types must be confirmed for the selected model. | PASS |

All three providers can support a structured JSON analysis flow in principle.

### 4.8 Price and operational constraints

| Provider | Finding | Grade |
|---|---|---|
| OpenAI API | Model pricing and rate limits vary by model, project, organization, and usage tier. Spend limits exist. | CONDITIONAL |
| Anthropic API | Rate limits, spend limits, usage tiers, and model pricing vary by tier/model. | CONDITIONAL |
| Google Gemini API | Free and paid tiers have materially different data policies; the pricing table must be interpreted per model and processing mode. Where the reviewed table lists Free Tier as used to improve products and Paid Tier as not used to improve products, only the paid path remains eligible for further review. This does not constitute approval of the paid path, and the selected model/tier must be rechecked before implementation. | CONDITIONAL |

Cost caps, timeout limits, retry limits, and per-request token limits must be configured before any real external AI use.

### 4.9 Contract analysis project fit

| Provider | Finding | Grade |
|---|---|---|
| OpenAI API | Technically suitable if only masked clause-level input is sent, raw request/response storage is blocked, ZDR or acceptable retention is confirmed, and PR-5 output safety is enforced. | CONDITIONAL |
| Anthropic API | Technically suitable if only masked clause-level input is sent, feedback submission is disabled/controlled, retention and covered model conditions are confirmed, and PR-5 output safety is enforced. | CONDITIONAL |
| Google Gemini API | Technically suitable only on paid quota, not free/unpaid quota, with explicit user disclosure, masked input only, and additional review of paid logging, regional processing, deletion behavior, and professional-advice restrictions. Paid tier as a category is not automatically PASS. | REVIEW |

No provider is approved for raw contract text transfer.

## 5. Provider-level decision table

| Provider | Overall grade | Reason |
|---|---|---|
| OpenAI API | CONDITIONAL | Good API fit and clear no-training-by-default language, but default API retention, human review exceptions, endpoint-specific retention, and ZDR eligibility must be controlled. |
| Anthropic API | CONDITIONAL | Clear commercial no-training-by-default and 30-day API deletion baseline, but covered model, retention exception, feedback, and exact enterprise controls need confirmation before real data use. |
| Google Gemini API | REVIEW | Paid API can be considered, but free/unpaid quota is blocked. Paid logging, regional processing, and professional-advice restrictions require additional review before MVP use. |

No provider is selected in this report.

## 6. Project-wide minimum safety conditions

These conditions apply regardless of provider.

- Never send real original contract text to an external AI provider.
- Send only PR-3-masked analysis input.
- Block external transfer if residual personal data is detected.
- Apply a strict outbound field allowlist.
- Do not store raw input.
- Do not store raw external response.
- Store only minimal metadata and normalized analysis results.
- Do not include contract body or personal data in logs.
- Run PR-5 output safety validation before user-visible display.
- Treat `reference_id` validation failure as BLOCK or REVIEW.
- Record provider policy version, source URLs, checked date, selected endpoint, and model version.
- Configure cost limits before any call.
- Configure timeout and retry limits before any call.
- Fail safely when the provider is unavailable or returns invalid output.
- Keep a provider-replaceable adapter boundary.
- Do not test with real personal data or real contract files without separate explicit approval.

## 7. Provider-independent architecture recommendation

The MVP should keep the existing provider adapter direction.

Recommended boundary:

```text
domain analysis request
-> masking and residual guard
-> outbound allowlist
-> provider adapter
-> response schema validation
-> reference_id validation
-> output safety checker
-> normalized result persistence
```

The core domain should not directly depend on a provider SDK. MVP implementation may start with one provider implementation only, but the interface should allow replacement.

## 8. MVP scope decision

Selected decision candidate:

```text
B. External AI use requires additional security and policy review before product use.
```

Reason:

- PR-2 to PR-5 show that local preprocessing, masking, usefulness preservation, and output safety checks are feasible on synthetic fixtures.
- Official provider policies do not justify sending raw contract text or raw personal data.
- At least one provider path, Google Gemini API free/unpaid quota, is incompatible with ContractCheck AI privacy goals.
- Even with paid/API paths, retention, human review exceptions, regional processing, and endpoint/model-specific behavior remain operational constraints.

MVP scope is not removed, but external AI use must be gated by the minimum safety conditions above.

## 9. Follow-up decisions

Required before any implementation that calls an external AI API:

- Select whether the MVP will use OpenAI API, Anthropic API, Google Gemini API paid quota, or defer external AI use.
- Confirm the exact endpoint and model.
- Confirm retention behavior for that endpoint and model.
- Confirm whether reduced-retention or ZDR-style controls are available and actually enabled.
- Confirm whether business, DPA, BAA, or enterprise terms are needed.
- Confirm user disclosure wording in v0.3 UX/policy design.
- Confirm outbound schema and allowlist in v0.4 API design.
- Confirm timeout, retry, and safe-failure behavior in v0.5 implementation design.

## 10. What this report does not approve

- Real contract processing
- Real personal data processing
- Raw contract transfer to external AI
- Free/unpaid Gemini API use for user contract analysis
- Consumer ChatGPT, Claude, or Gemini policy reuse for API decisions
- Provider selection
- API key preparation
- External AI API calls
- Provider adapter implementation
- Legal advice or legal safety guarantee
- Production release

## 11. PR-6 status

- Official policy research: completed
- Independent review: completed
- GitHub reflection: PR #25 merged
- Provider selection: not selected
- External AI API call: not performed
- Real contract or personal data use: not performed
- PR-6: completed
- v0.2.1 technical validation phase: completed
- Product use approval: not granted
- Production release approval: not granted
