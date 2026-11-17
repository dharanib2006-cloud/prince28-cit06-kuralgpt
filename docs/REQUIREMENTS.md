# KuralGPT - Project Requirements

## 1. Functional Requirements

These requirements describe what KuralGPT must do.

| ID | Requirement | Measurable Target |
|---|---|---|
| FR-01 | The system shall allow teachers to search for Thirukkural couplets using a value, theme, situation, or keyword. | Return relevant results within 3 seconds for at least 90% of test queries. |
| FR-02 | The system shall display the original Tamil couplet with its Kural number. | Display the correct couplet and number for 100% of verified records. |
| FR-03 | The system shall provide simple Tamil and English meanings for each available Kural. | Display both meanings for 100% of records where verified translations are available. |
| FR-04 | The system shall show the related value or theme for each retrieved Kural. | Display at least one relevant theme for 100% of verified records. |
| FR-05 | The system shall provide an API to retrieve Kural records individually and as a list. | Successfully handle all valid test requests and return appropriate errors for invalid requests. |

## 2. Non-Functional Requirements

These requirements describe the quality and performance expected from KuralGPT.

| ID | Requirement | Measurable Target |
|---|---|---|
| NFR-01 | Performance: The API should respond quickly to teacher search and retrieval requests. | 95% of requests should complete within 2 seconds under normal local testing conditions. |
| NFR-02 | Accuracy: The system must not invent or misquote Thirukkural couplets. | Zero invented or misquoted Kurals in a test set of 100 answers. |
| NFR-03 | Reliability: The application should provide clear health and readiness status. | `/health` should return HTTP 200 when the application is running; `/ready` should report whether the data is available. |
| NFR-04 | Maintainability: The project should follow consistent Python code-quality standards. | Ruff checks and all automated tests should pass before merging changes. |
| NFR-05 | Security: The application must not expose secret keys or environment-specific credentials in the public repository. | Zero committed `.env` files, private keys, or detected secrets. |