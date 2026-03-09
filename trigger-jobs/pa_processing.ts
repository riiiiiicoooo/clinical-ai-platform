import { TriggerClient, eventTrigger } from "@trigger.dev/sdk";

const client = new TriggerClient({ id: "clinical-ai-platform" });

client.defineJob({
  id: "prior-auth-processing",
  name: "Prior Authorization Processing",
  version: "1.0.0",
  trigger: eventTrigger({ name: "pa.request.submitted" }),

  run: async (payload, io) => {
    const { pa_id, patient_id, cpt_code, payer_id } = payload;

    // Step 1: Fetch patient clinical data via FHIR
    const patientData = await io.runTask("fetch-patient-data", async () => {
      const response = await fetch(
        `${process.env.API_URL}/api/v1/fhir/patient/${patient_id}/summary`
      );
      return response.json();
    });

    await io.logger.info("Patient data fetched", { patient_id });

    // Step 2: Run NLP extraction on clinical notes
    const nlpResults = await io.runTask("nlp-extraction", async () => {
      const response = await fetch(`${process.env.API_URL}/api/v1/nlp/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id,
          encounter_notes: patientData.recent_encounters,
        }),
      });
      return response.json();
    });

    // Step 3: Generate PA request via AI agent
    const paResult = await io.runTask("generate-pa", async () => {
      const response = await fetch(
        `${process.env.API_URL}/api/v1/prior-auth/generate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            patient_id,
            cpt_code,
            payer_id,
            provider_id: payload.provider_id,
            nlp_extraction: nlpResults,
          }),
        }
      );
      return response.json();
    });

    await io.logger.info("PA generated", {
      pa_id: paResult.pa_id,
      status: paResult.status,
      generation_time_ms: paResult.generation_time_ms,
    });

    // Step 4: Submit to payer (if auto-submit enabled)
    if (payload.auto_submit && paResult.status === "pending_review") {
      const submission = await io.runTask("submit-pa", async () => {
        const response = await fetch(
          `${process.env.API_URL}/api/v1/prior-auth/submit`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pa_id: paResult.pa_id }),
          }
        );
        return response.json();
      });

      await io.logger.info("PA submitted", {
        tracking_id: submission.tracking_id,
        method: submission.method,
      });
    }

    return { pa_id: paResult.pa_id, status: paResult.status };
  },
});
