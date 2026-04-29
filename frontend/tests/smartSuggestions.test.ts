import assert from "node:assert/strict";

import {
    SMART_SUGGESTION_DEBOUNCE_MS,
    buildSuggestionTagOverrides,
    getSuggestionApplyPayload,
    getSuggestionCopyText,
    shouldCommitSuggestionResponse,
    shouldGenerateSmartSuggestions,
} from "../src/lib/smartSuggestions.ts";
import type { SmartSuggestion } from "../src/lib/types.ts";

const mobileSuggestion: SmartSuggestion = {
    id: "smart-impact-review",
    title: "Review the impact classification",
    category: "Customer Experience",
    explanation: "The wording points to a customer-experience outcome.",
    improved_pitch: "Improve mobile UX to increase customer satisfaction and reduce the time required to complete key user journeys.",
    next_action: "Consider adding CustomerExperience alongside Cost.",
    confidence: "medium",
    action_type: "apply_tag",
    suggested_tags: ["CustomerExperience"],
};

assert.equal(shouldGenerateSmartSuggestions("ux"), false);
assert.equal(shouldGenerateSmartSuggestions("improve mobile ux"), true);

assert.ok(SMART_SUGGESTION_DEBOUNCE_MS >= 500);
assert.ok(SMART_SUGGESTION_DEBOUNCE_MS <= 800);

assert.equal(
    getSuggestionCopyText(mobileSuggestion),
    "Improve mobile UX to increase customer satisfaction and reduce the time required to complete key user journeys.",
);

const applyPitchSuggestion: SmartSuggestion = {
    id: "smart-business-framing",
    title: "Clarify the measurable business outcome",
    category: "Business Framing",
    explanation: "The pitch needs a measurable outcome.",
    improved_pitch: "Improve the mobile user experience to reduce task completion time and lower support requests.",
    next_action: "Add baseline and target KPIs.",
    confidence: "high",
    action_type: "apply_pitch",
};

assert.deepEqual(getSuggestionApplyPayload(applyPitchSuggestion), {
    nextPitch: "Improve the mobile user experience to reduce task completion time and lower support requests.",
});

assert.deepEqual(buildSuggestionTagOverrides(["CustomerExperience"]), {
    domains: [],
    impacts: ["CustomerExperience"],
});

assert.deepEqual(getSuggestionApplyPayload(mobileSuggestion), {
    tagOverrides: {
        domains: [],
        impacts: ["CustomerExperience"],
    },
});

assert.equal(shouldCommitSuggestionResponse(2, 3), false);
assert.equal(shouldCommitSuggestionResponse(4, 4), true);

console.log("smartSuggestions.test.ts passed");
