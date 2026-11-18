package org.llmsport;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.regex.Pattern;

record WorkoutCalculator(String text, String activity, List<WorkoutCalculator.Measure> measures) {
    private static final String DURATION = "duration";
    private static final String DISTANCE = "distance";
    private static final String SETS = "sets";
    private static final String REPETITIONS = "repetitions";
    private static final String LOAD = "load";

    private static final Pattern NUMBER = pattern("(?<![\\w.,+−-])([+−-]?[0-9]+(?:[.,][0-9]+)?)");
    private static final Pattern LABEL = pattern("\\b(dur[ée]e|distance(?:\\s+parcourue)?|charge)\\s*:?\\s*$");
    private static final Pattern RUN_DISTANCE = pattern("\\b(couru|course(?:\\s+à\\s+pied)?)\\s*:?\\s*$");
    private static final Pattern LIFT_LOAD = pattern("\\b(?:r[ée]p[ée]titions?|reps?)\\s*,?\\s+à\\s*$");
    private static final Pattern ELAPSED_TIME = pattern("\\bpendant\\s*$");
    private static final Pattern NEGATED = pattern("\\b(?:pas|ni|au lieu de)\\s*$");
    private static final Pattern ADDITIVE = pattern("\\s*,?\\s*(?:puis|et)\\s*");
    private static final Pattern PER_SET = pattern("\\s+de\\s+");
    private static final Pattern WHITESPACE = pattern("\\s*");
    private static final Map<String, Pattern> ACTIVITIES = Map.of(
            "running", pattern("\\b(?:course|couru)\\b"),
            "cycling", pattern("\\b(?:vélo|velo|cyclisme|bicyclette)\\b"),
            "squat", pattern("\\bsquats?\\b"),
            "mobility", pattern("\\bmobilit[ée]\\b"));
    private static final Map<String, Integer> TIME_IN_SECONDS = Map.of("s", 1, "min", 60, "h", 3600);

    private enum Unit {
        SECONDS(DURATION, "s", "secondes?|secs?|s"),
        MINUTES(DURATION, "min", "minutes?|mins?"),
        HOURS(DURATION, "h", "heures?|h"),
        METERS(DISTANCE, "m", "m[èe]tres?|m"),
        KILOMETERS(DISTANCE, "km", "kilom[èe]tres?|km"),
        SET_COUNT(SETS, "count", "s[ée]ries?"),
        REP_COUNT(REPETITIONS, "count", "r[ée]p[ée]titions?|reps?"),
        KILOGRAMS(LOAD, "kg", "kilogrammes?|kilos?|kg");

        final String field;
        final String code;
        final Pattern spelling;

        Unit(String field, String code, String spelling) {
            this.field = field;
            this.code = code;
            this.spelling = pattern("\\s*(?:" + spelling + ")\\b");
        }
    }

    record Measure(String field, BigDecimal value, String unit, int start, int end) {}

    static final class InvalidDeclaration extends IllegalArgumentException {
        InvalidDeclaration(String code) {
            super(code);
        }
    }

    private static Pattern pattern(String expression) {
        return Pattern.compile(expression, Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CHARACTER_CLASS);
    }

    static WorkoutCalculator parse(String text) {
        var activities = ACTIVITIES.entrySet().stream()
                .filter(entry -> entry.getValue().matcher(text).find()).map(Map.Entry::getKey).toList();
        if (activities.size() > 1) throw new InvalidDeclaration("ambiguous_activity");
        var activity = activities.isEmpty() ? null : activities.get(0);

        List<Measure> measures = new ArrayList<>();
        var number = NUMBER.matcher(text);
        while (number.find()) {
            String prefix = text.substring(0, number.start());
            if (NEGATED.matcher(prefix).find()) continue;
            int end = number.end();
            Unit unit = null;
            for (var candidate : Unit.values()) {
                var matcher = candidate.spelling.matcher(text).region(end, text.length());
                if (matcher.lookingAt()) {
                    unit = candidate;
                    end = matcher.end();
                    break;
                }
            }
            String field = labelledField(prefix);
            if (unit != null) {
                if (field != null && !field.equals(unit.field)) throw new InvalidDeclaration("invalid_measure_unit");
                field = unit.field;
            } else if (field == null) {
                field = unresolvedField(prefix);
            }
            if (field == null) continue;
            BigDecimal value = new BigDecimal(number.group(1).replace(',', '.').replace('−', '-'));
            if (value.signum() < 0) {
                throw new InvalidDeclaration(DURATION.equals(field) ? "negative_duration" : "negative_measure");
            }
            if (unit != null && "count".equals(unit.code) && value.stripTrailingZeros().scale() > 0) {
                throw new InvalidDeclaration("invalid_count");
            }
            measures.add(new Measure(field, value, unit == null ? null : unit.code, number.start(), end));
        }
        return new WorkoutCalculator(text, activity, List.copyOf(measures));
    }

    private static String labelledField(String prefix) {
        var label = LABEL.matcher(prefix);
        if (!label.find()) return null;
        var name = label.group(1).toLowerCase(Locale.ROOT);
        if (name.startsWith("dist")) return DISTANCE;
        return name.equals("charge") ? LOAD : DURATION;
    }

    private static String unresolvedField(String prefix) {
        if (RUN_DISTANCE.matcher(prefix).find()) return DISTANCE;
        if (LIFT_LOAD.matcher(prefix).find()) return LOAD;
        if (ELAPSED_TIME.matcher(prefix).find()) return DURATION;
        return null;
    }

    ObjectNode calculate(ObjectMapper mapper, JsonNode input, JsonNode proposal) {
        var source = source(mapper, input, text);
        var mentions = proposal.path("sport_mentions");
        var mention = mentions.path(0);
        var claims = mention.path("measures");
        check(mentions.size() == 1 && text.equals(mention.path("text").textValue())
                && sameSource(mention.path("source"), source)
                && Objects.equals(activity, mention.path("activity").textValue())
                && measures.size() == claims.size());

        var result = mapper.createObjectNode().put("entry_kind", "workout").put("activity", activity);
        result.set("entry_id", input.get("entry_id"));
        result.set("entry_revision", input.get("entry_revision"));
        result.set("proposal_id", proposal.get("proposal_id"));
        result.set("proposal_schema_version", proposal.get("schema_version"));
        result.set("source", source);
        result.putNull("energy_burned");
        var declared = result.putArray("measures");
        for (int i = 0; i < measures.size(); i++) {
            Measure measure = measures.get(i);
            var claim = claims.get(i);
            var origin = source(mapper, input, fragment(measure));
            check(measure.field.equals(claim.path("id").textValue()) && claim.path("value").isNumber()
                    && measure.value.compareTo(claim.path("value").decimalValue()) == 0
                    && Objects.equals(measure.unit, claim.path("unit").textValue())
                    && sameSource(claim.path("source"), origin));
            declared.addObject().put("id", measure.field).put("value", measure.value)
                    .put("unit", measure.unit).set("source", origin);
        }

        var summary = result.putObject("summary");
        var clarifications = result.putArray("clarifications");
        for (String field : List.of(DURATION, DISTANCE, SETS, REPETITIONS, LOAD)) {
            var parts = measures.stream().filter(measure -> field.equals(measure.field)).toList();
            var row = summary.putObject(field);
            var origins = row.putArray("sources");
            parts.forEach(part -> origins.add(source(mapper, input, fragment(part))));
            if (parts.isEmpty()) {
                unknown(row, "absent");
                continue;
            }
            var unresolved = parts.stream().filter(part -> part.unit == null).findFirst();
            if (unresolved.isPresent()) {
                unknown(row, "unresolved");
                if (clarifications.isEmpty()) {
                    String number = fragment(unresolved.get());
                    String question = LOAD.equals(field) ? "Dans quelle unité est exprimée la charge de " + number + " ?"
                            : "Quelle unité correspond au nombre " + number + " ?";
                    clarify(clarifications.addObject(), field + ".unit", "unit_absent", question);
                }
            } else if (parts.size() > 1 && !additive(field, parts)) {
                unknown(row, "unresolved");
                if (clarifications.isEmpty()) {
                    clarify(clarifications.addObject(), field, "other", "Quelle valeur faut-il retenir pour cette mesure ?");
                }
            } else {
                String unit = summaryUnit(field, parts);
                BigDecimal value = parts.stream().map(part -> converted(part, unit)).reduce(BigDecimal.ZERO, BigDecimal::add);
                String operation = parts.size() > 1 ? "sum" : unit.equals(parts.get(0).unit) ? "declared" : "unit_conversion";
                known(row, value, unit, operation);
            }
        }
        totalRepetitions(mapper, input, summary.putObject("total_repetitions"));
        if (clarifications.isEmpty() && activity == null) {
            clarify(clarifications.addObject(), "activity", "activity_ambiguous", "Quelle activité as-tu pratiquée ?");
        } else if (clarifications.isEmpty() && measures.isEmpty()) {
            String question = "running".equals(activity) ? "Combien de temps as-tu couru ?" : "Combien de temps a duré la séance ?";
            clarify(clarifications.addObject(), DURATION, "quantity_absent", question);
        }
        return result;
    }

    private void totalRepetitions(ObjectMapper mapper, JsonNode input, ObjectNode row) {
        var origins = row.putArray("sources");
        var sets = measures.stream().filter(measure -> SETS.equals(measure.field)).toList();
        var reps = measures.stream().filter(measure -> REPETITIONS.equals(measure.field)).toList();
        if (sets.size() == 1 && reps.size() == 1 && sets.get(0).end <= reps.get(0).start
                && PER_SET.matcher(text.substring(sets.get(0).end, reps.get(0).start)).matches()) {
            origins.add(source(mapper, input, fragment(sets.get(0))));
            origins.add(source(mapper, input, fragment(reps.get(0))));
            known(row, sets.get(0).value.multiply(reps.get(0).value), "count", "product");
        } else {
            unknown(row, "absent");
        }
    }

    private boolean additive(String field, List<Measure> parts) {
        if (!DURATION.equals(field) && !DISTANCE.equals(field)) return false;
        for (int i = 1; i < parts.size(); i++) {
            Measure previous = parts.get(i - 1);
            Measure current = parts.get(i);
            String separator = text.substring(previous.end, current.start);
            if (ADDITIVE.matcher(separator).matches()) continue;
            if (!(DURATION.equals(field) && WHITESPACE.matcher(separator).matches()
                    && TIME_IN_SECONDS.get(previous.unit) > TIME_IN_SECONDS.get(current.unit))) return false;
        }
        return true;
    }

    private static String summaryUnit(String field, List<Measure> parts) {
        if (DISTANCE.equals(field)) return "m";
        if (DURATION.equals(field)) return parts.stream().anyMatch(part -> "s".equals(part.unit)) ? "s" : "min";
        return parts.get(0).unit;
    }

    private static BigDecimal converted(Measure part, String unit) {
        if ("km".equals(part.unit)) return part.value.scaleByPowerOfTen(3);
        if ("h".equals(part.unit)) return part.value.multiply(BigDecimal.valueOf("s".equals(unit) ? 3600 : 60));
        if ("min".equals(part.unit) && "s".equals(unit)) return part.value.multiply(BigDecimal.valueOf(60));
        return part.value;
    }

    private String fragment(Measure measure) {
        return text.substring(measure.start, measure.end);
    }

    private static void known(ObjectNode row, BigDecimal value, String unit, String operation) {
        row.put("value", value).put("unit", unit).put("status", "known").put("operation", operation);
    }

    private static void unknown(ObjectNode row, String status) {
        row.putNull("value").putNull("unit").put("status", status);
    }

    private static void clarify(ObjectNode target, String field, String reason, String question) {
        target.put("field", field).put("reason", reason).put("question", question);
    }

    private static ObjectNode source(ObjectMapper mapper, JsonNode input, String text) {
        var source = mapper.createObjectNode().put("kind", "user_declaration").put("text", text);
        source.set("input_id", input.get("entry_id"));
        source.set("input_revision", input.get("entry_revision"));
        return source;
    }

    private static boolean sameSource(JsonNode claim, ObjectNode source) {
        return source.path("kind").equals(claim.path("kind")) && source.path("text").equals(claim.path("text"))
                && source.path("input_id").equals(claim.path("input_id"))
                && source.path("input_revision").decimalValue().compareTo(claim.path("input_revision").decimalValue()) == 0;
    }

    private static void check(boolean condition) {
        if (!condition) throw new IllegalArgumentException("invalid_proposal");
    }
}
