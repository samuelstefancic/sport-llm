package org.llmsport;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.util.LinkedHashSet;
import java.util.Set;
import java.util.TreeSet;

record JournalDeclaration(ObjectNode envelope, ObjectNode body) {
    static JournalDeclaration parse(String kind, JsonNode input) {
        if (!input.isObject()) throw new IllegalArgumentException("invalid_request");
        ObjectNode envelope = ((ObjectNode) input).deepCopy();
        boolean meal = kind.equals("meal");
        JsonNode selected = meal ? envelope.remove("selected_nutrients") : null;
        JsonNode corrected = meal ? envelope.remove("corrected_mentions") : null;
        if (!ProposalClient.validInput(envelope) || (corrected != null &&
                (!corrected.isArray() || envelope.path("entry_revision").longValue() <= 1))) {
            throw new IllegalArgumentException("invalid_request");
        }

        ObjectNode body = envelope.deepCopy().put("entry_kind", kind);
        if (meal) {
            var selection = body.putArray("selected_nutrients");
            if (selected == null) {
                MealCalculator.DEFAULTS.forEach(selection::add);
            } else {
                if (selected.isEmpty() || selected.size() > 64) throw new MealCalculator.InvalidSelection();
                var ordered = new LinkedHashSet<String>();
                readUniqueText(selected, ordered, new MealCalculator.InvalidSelection());
                ordered.forEach(selection::add);
            }
            var corrections = body.putArray("corrected_mentions");
            if (corrected != null) {
                var sorted = new TreeSet<String>();
                readUniqueText(corrected, sorted, new MealCalculator.InvalidCorrection());
                sorted.forEach(corrections::add);
            }
        }
        return new JournalDeclaration(envelope, body);
    }

    static JournalDeclaration fromRevisionPath(String kind, String id, long revision, JsonNode input) {
        if (!input.isObject() || input.has("entry_id") || input.has("entry_revision")) {
            throw new IllegalArgumentException("invalid_request");
        }
        return parse(kind, ((ObjectNode) input).deepCopy().put("entry_id", id).put("entry_revision", revision));
    }

    private static void readUniqueText(JsonNode values, Set<String> target, IllegalArgumentException error) {
        if (!values.isArray()) throw error;
        for (var value : values) {
            if (!value.isTextual() || !target.add(value.textValue())) throw error;
        }
    }

    String id() { return envelope.path("entry_id").textValue(); }

    long revision() { return envelope.path("entry_revision").longValue(); }

    String text() { return envelope.path("text").textValue(); }

    String kind() { return body.path("entry_kind").textValue(); }
}
