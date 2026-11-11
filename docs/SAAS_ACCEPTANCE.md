# Testing and acceptance

Run the backend and frontend suites from the [setup guide](../README.md#testing). The backend tests cover account isolation, upload reading, automatic workflows, citation validation, witness handling, map consent and PayPal boundaries. Frontend tests cover the corresponding rendered states. CI also builds and starts the production container.

For external integration acceptance, use a dedicated test Supabase project and authorized Sandbox credentials. The scripts in [scripts](../scripts) can create accounts, cases and uploads. Run them only on an environment intended for test records. Run `python scripts/saas_acceptance.py --help` for the persistence workflow and `python scripts/saas_paypal_acceptance.py --help` for Sandbox verification. Test state belongs under ignored runtime paths.

The pre-cleanup branch preserves the historical release and acceptance records. Frozen model evaluation protocols and outputs remain in [evaluation](../evaluation). [Historical release evidence](https://github.com/harshil0014/verdict-ai/tree/backup/pre-cleanup/docs)