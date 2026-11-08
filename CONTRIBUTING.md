# Contributing

Use one scoped issue per independently reviewable change. State its failure or requirement, reproduction, acceptance criteria and test command. Include a regression case for bugs. Avoid unrelated refactors. Do not commit credentials, personal records or production data. Label generated fixtures clearly. Do not describe an issue as resolved until the relevant checks pass.

The fault-scenarios suite tests actual SQLite transactions and a real child-process crash. Keep tests deterministic; public RPC calls belong only in the opt-in pilot.
