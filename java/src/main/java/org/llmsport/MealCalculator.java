package org.llmsport;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.math.BigDecimal;
import java.math.MathContext;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

final class MealCalculator {
    private static final String CATALOG = "DEMO-FOOD";
    private static final List<String> DEFAULTS = List.of("energy", "protein", "carbohydrate", "fat");
    private static final int FR = Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE | Pattern.UNICODE_CHARACTER_CLASS;
    private static final Pattern DISPLAY = Pattern.compile("[.!?]\\s*affiche\\b[^.!?]*[.!?]?\\s*$", FR);
    private static final Pattern SPLIT = Pattern.compile("(?<![0-9]),|,(?![0-9])|;|\\s+et\\s+", FR);
    private static final Pattern MASS = Pattern.compile(
            "^(?:([+-]?[0-9]+(?:[.,][0-9]+)?)\\s*(kg|g|ml|l|portions?|bols?)?|un\\s+bol)"
                    + "(?![\\p{L}0-9.,])\\s*", FR);
    private static final Pattern STATED_STATES = Pattern.compile("\\b(cuit(?:e)?s?|cru(?:e)?s?)\\b", FR);
    private static final Pattern STATE = Pattern.compile("\\s+(cuit(?:e)?s?|cru(?:e)?s?)$", FR);
    private static final Pattern FOOD_ID = Pattern.compile("\\s+de la fiche ([\\w.:-]+)$", FR);
    private static final Pattern ARTICLE = Pattern.compile("^(?:(?:de la|de|du|des|le|la|les)\\s+|[dl]['’])", FR);

    static final class InvalidSelection extends IllegalArgumentException {
        InvalidSelection() { super("invalid_selection"); }
    }

    static final class InvalidCorrection extends IllegalArgumentException {
        InvalidCorrection() { super("invalid_correction"); }
    }

    static final class NegativeQuantity extends IllegalArgumentException {
        NegativeQuantity() { super("negative_quantity"); }
    }

    private record Food(String id, String label, String state, BigDecimal basis, Map<String, BigDecimal> values) {}
    private record Catalog(String version, Map<String, Food> foods, Map<String, String> units) {}
    private record Portion(String id, ObjectNode source, BigDecimal grams, Food food, String missing) {}

    // A single SELECT pins the active version, its foods and its reference values to one snapshot.
    private static Catalog catalog(Connection db) throws SQLException {
        String query = """
                SELECT a.version, f.food_id, f.label, f.state, f.basis_value, n.nutrient_id, n.unit, n.value
                FROM catalog_active a JOIN catalog_food f USING (catalog_id, version)
                JOIN catalog_nutrient n USING (catalog_id, version, food_id)
                WHERE a.catalog_id = ? ORDER BY f.food_id, n.nutrient_id
                """;
        Map<String, Food> foods = new LinkedHashMap<>();
        Map<String, String> units = new HashMap<>();
        String version = null;
        try (var statement = db.prepareStatement(query)) {
            statement.setString(1, CATALOG);
            try (var rows = statement.executeQuery()) {
                while (rows.next()) {
                    version = rows.getString("version");
                    String id = rows.getString("food_id");
                    Food food = foods.get(id);
                    if (food == null) {
                        food = new Food(id, rows.getString("label"), rows.getString("state"),
                                rows.getBigDecimal("basis_value"), new HashMap<>());
                        foods.put(id, food);
                    }
                    String nutrient = rows.getString("nutrient_id");
                    units.put(nutrient, rows.getString("unit"));
                    food.values.put(nutrient, rows.getBigDecimal("value"));
                }
            }
        }
        if (version == null) throw new SQLException("Catalogue actif indisponible");
        return new Catalog(version, foods, units);
    }

    private static List<String> selection(JsonNode selected, Catalog catalog) {
        List<String> ids = new ArrayList<>();
        if (selected == null || selected.isMissingNode()) {
            ids.addAll(DEFAULTS);
        } else {
            if (!selected.isArray() || selected.isEmpty() || selected.size() > 64) throw new InvalidSelection();
            for (JsonNode value : selected) {
                if (!value.isTextual() || ids.contains(value.textValue())) throw new InvalidSelection();
                ids.add(value.textValue());
            }
        }
        if (!catalog.units.keySet().containsAll(ids)) throw new InvalidSelection();
        return ids;
    }

    private static String trim(String phrase) {
        return phrase.replaceAll("(?U)^\\s+|[.!?\\s]+$", "");
    }

    private static void check(boolean condition) {
        if (!condition) throw new IllegalArgumentException("invalid_proposal");
    }

    private static boolean sameLabel(String label, String wording) {
        if (label.equalsIgnoreCase(wording)) return true;
        return label.length() > 2 && (label + "s").equalsIgnoreCase(wording)
                || wording.length() > 2 && (wording + "s").equalsIgnoreCase(label);
    }

    private static Portion portion(ObjectMapper mapper, JsonNode input, JsonNode mention, String phrase, Catalog catalog, boolean corrected) {
        JsonNode source = mention.path("source");
        check(phrase.equals(mention.path("text").textValue()) && phrase.equals(source.path("text").textValue())
                && input.path("entry_id").equals(source.path("input_id"))
                && input.path("entry_revision").decimalValue().compareTo(source.path("input_revision").decimalValue()) == 0
                && "user_declaration".equals(source.path("kind").textValue()));

        ObjectNode origin = mapper.createObjectNode().put("kind", corrected ? "user_correction" : "user_declaration");
        origin.set("input_id", input.get("entry_id"));
        origin.set("input_revision", input.get("entry_revision"));
        origin.put("text", phrase);

        String wording = phrase;
        Matcher amount = MASS.matcher(wording);
        BigDecimal value = null;
        String unit = null;
        if (amount.find()) {
            String number = amount.group(1);
            value = number == null ? BigDecimal.ONE : new BigDecimal(number.replace(',', '.'));
            if (value.signum() < 0) throw new NegativeQuantity();
            unit = number == null ? "portion" : amount.group(2);
            if (unit != null) {
                unit = unit.toLowerCase(Locale.ROOT);
                if (unit.equals("portions") || unit.equals("bol") || unit.equals("bols")) unit = "portion";
            }
            wording = wording.substring(amount.end());
        }
        JsonNode quantity = mention.path("quantity");
        if (!quantity.isNull()) {
            check(value != null && unit != null && quantity.isObject()
                    && unit.equals(quantity.path("unit").textValue())
                    && value.compareTo(quantity.path("value").decimalValue()) == 0
                    && source.equals(quantity.path("source")));
        }

        Matcher record = FOOD_ID.matcher(wording);
        String recordId = null;
        if (record.find()) {
            recordId = record.group(1);
            wording = wording.substring(0, record.start());
        }
        Matcher stated = STATE.matcher(wording);
        String state = "unknown";
        if (stated.find()) {
            state = stated.group(1).toLowerCase(Locale.ROOT).startsWith("cuit") ? "cooked" : "raw";
            wording = wording.substring(0, stated.start());
        }
        String label = ARTICLE.matcher(wording).replaceFirst("").strip();
        List<Food> matching = catalog.foods.values().stream()
                .filter(food -> sameLabel(food.label, label)).toList();
        if (state.equals("unknown") && matching.size() == 1 && matching.get(0).state.equals("not_applicable")) {
            state = "not_applicable";
        }
        String claimedState = mention.path("food_state").asText();
        if (!claimedState.equals("unknown") && !claimedState.equals(state)) {
            // An unrecognised dish can still contain an explicit state (e.g. « riz cuit au curry »).
            // Keeping it unresolved is safer than assigning it to the plain rice reference.
            Set<String> statedStates = new HashSet<>();
            Matcher words = STATED_STATES.matcher(phrase);
            while (words.find()) {
                statedStates.add(words.group(1).toLowerCase(Locale.ROOT).startsWith("cuit") ? "cooked" : "raw");
            }
            check(statedStates.equals(Set.of(claimedState)));
        }

        String resolvedState = state;
        List<Food> compatible = matching.stream().filter(food -> food.state.equals(resolvedState)).toList();
        Food food = !state.equals("unknown") && compatible.size() == 1 ? compatible.get(0) : null;
        if (recordId != null && (food == null || !recordId.equals(food.id))) food = null;
        for (JsonNode candidate : mention.path("catalog_candidates")) {
            check(food != null && food.id.equals(candidate.path("record_id").asText())
                    && catalog.version.equals(candidate.path("catalog_version").asText())
                    && CATALOG.equals(candidate.path("catalog_id").asText()));
        }

        String missing = null;
        BigDecimal grams = null;
        if (matching.isEmpty()) missing = "food_unresolved";
        else if (state.equals("unknown")) missing = "raw_cooked_unknown";
        else if (food == null) missing = "food_unresolved";
        else if (value == null) missing = "quantity_absent";
        else if (unit == null) missing = "unit_absent";
        else if (quantity.isNull()) missing = "quantity_absent";
        else if (unit.equals("portion")) missing = "portion_mass_unknown";
        else if (unit.equals("ml") || unit.equals("l")) missing = "density_unknown";
        else grams = unit.equals("kg") ? value.movePointRight(3) : value;
        return new Portion(mention.path("mention_id").asText(), origin, grams, food, missing);
    }

    private static ObjectNode referenceSource(ObjectMapper mapper, Catalog catalog, Food food, String nutrient) {
        return mapper.createObjectNode().put("kind", "catalog").put("catalog_id", CATALOG)
                .put("catalog_version", catalog.version).put("record_id", food.id).put("field", "nutrients." + nutrient);
    }

    private static String question(String reason) {
        return switch (reason) {
            case "quantity_absent" -> "Quelle masse avez-vous consommée ?";
            case "unit_absent" -> "Quelle est l’unité de la quantité déclarée ?";
            case "raw_cooked_unknown" -> "L’aliment a-t-il été pesé cru ou cuit ?";
            case "portion_mass_unknown", "density_unknown" -> "Quelle masse en grammes représente cette quantité ?";
            default -> "Quelle fiche alimentaire correspond à cet aliment ?";
        };
    }

    private static ObjectNode nutrient(ObjectMapper mapper, Catalog catalog, List<Portion> portions, String id) {
        String unit = catalog.units.get(id);
        ObjectNode row = mapper.createObjectNode().put("id", id).put("unit", unit);
        ArrayNode contributions = row.putArray("provenance");
        ArrayNode missing = row.putArray("missing");
        BigDecimal total = BigDecimal.ZERO;
        for (Portion p : portions) {
            if (p.missing != null) {
                missing.addObject().put("item_id", p.id).put("reason", p.missing)
                        .put("detail", question(p.missing)).set("source", p.source);
                continue;
            }
            ObjectNode referenceSource = referenceSource(mapper, catalog, p.food, id);
            BigDecimal referenceValue = p.food.values.get(id);
            if (referenceValue == null) {
                missing.addObject().put("item_id", p.id).put("reason", "catalog_value_absent")
                        .put("detail", id + " absent de la fiche " + p.food.id).set("source", referenceSource);
                continue;
            }
            BigDecimal product = p.grams.multiply(referenceValue);
            BigDecimal contribution;
            try {
                contribution = product.divide(p.food.basis);
            } catch (ArithmeticException repeatingDecimal) {
                contribution = product.divide(p.food.basis, MathContext.DECIMAL128);
            }
            ObjectNode part = contributions.addObject().put("item_id", p.id).put("value", contribution);
            part.putObject("quantity").put("value", p.grams).put("unit", "g").set("source", p.source);
            part.putObject("reference").put("value", referenceValue).put("unit", unit)
                    .put("basis_mass_g", p.food.basis).set("source", referenceSource);
            total = total.add(contribution);
        }
        if (contributions.isEmpty()) {
            row.putNull("value").put("status", "indéterminé");
        } else {
            row.put("value", total).put("status", missing.isEmpty() ? "complet" : "partiel");
        }
        return row;
    }

    static ObjectNode calculate(Connection db, ObjectMapper mapper, JsonNode input, JsonNode proposal, JsonNode selected)
            throws SQLException {
        Catalog catalog = catalog(db);
        List<String> ids = selection(selected, catalog);
        String declaration = DISPLAY.matcher(input.path("text").asText()).replaceFirst("");
        List<String> fragments = SPLIT.splitAsStream(declaration).map(MealCalculator::trim)
                .filter(fragment -> !fragment.isEmpty()).toList();
        if (fragments.isEmpty()) fragments = List.of(input.path("text").asText());
        JsonNode mentions = proposal.path("food_mentions");
        check(mentions.size() == fragments.size());
        Set<String> corrected = new HashSet<>();
        JsonNode corrections = input.get("corrected_mentions");
        if (corrections != null) {
            if (!corrections.isArray()) throw new InvalidCorrection();
            for (JsonNode mark : corrections) {
                if (!mark.isTextual() || !corrected.add(mark.textValue())) throw new InvalidCorrection();
            }
        }
        Set<String> seen = new HashSet<>();
        List<Portion> portions = new ArrayList<>();
        ObjectNode result = mapper.createObjectNode();
        ArrayNode questions = result.putArray("clarifications");
        for (int i = 0; i < fragments.size(); i++) {
            // Public correction IDs refer to positions in this exact revision of the declaration.
            String position = "m" + (i + 1);
            if (!corrected.isEmpty()) check(position.equals(mentions.get(i).path("mention_id").asText()));
            Portion p = portion(mapper, input, mentions.get(i), fragments.get(i), catalog, corrected.contains(position));
            check(seen.add(p.id));
            portions.add(p);
            if (p.missing != null) {
                questions.addObject().put("mention_id", p.id).put("reason", p.missing)
                        .put("field", p.missing.equals("food_unresolved") ? "food" :
                                p.missing.equals("raw_cooked_unknown") ? "food_state" : "quantity")
                        .put("question", question(p.missing));
            }
        }
        if (!seen.containsAll(corrected)) throw new InvalidCorrection();
        ObjectNode report = result.putObject("report").put("kind", "java_nutrition_report")
                .put("schema_version", "0.1.0").put("meal_id", input.path("entry_id").asText())
                .put("calculation", "sum_known_contributions_v1");
        report.set("meal_revision", input.get("entry_revision"));
        ArrayNode selection = report.putArray("selected_nutrients");
        ArrayNode rows = report.putArray("nutrients");
        for (String id : ids) {
            selection.add(id);
            rows.add(nutrient(mapper, catalog, portions, id));
        }
        return result;
    }
}
