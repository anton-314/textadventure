import pytest

from textadventure.parser import Command, parse, parse_command, parse_with_tool

# Pro Verb mehrere Schreibweisen -> gleiches (Verb, Objekt)
SYNONYMS = [
    # go
    ("gehe norden", ("go", "norden")), ("geh nord", ("go", "norden")), ("gehen n", ("go", "norden")),
    ("laufe nach oben", ("go", "oben")), ("renne runter", ("go", "unten")), ("go west", ("go", "westen")),
    ("wandere sueden", ("go", "süden")), ("gehe süd", ("go", "süden")), ("bewege dich osten", ("go", "osten")),
    ("begib dich hoch", ("go", "oben")), ("walk ost", ("go", "osten")),
    # look
    ("schau", ("look", "")), ("umgucken", ("look", "")), ("gucken", ("look", "")), ("umsehen", ("look", "")),
    ("umschauen", ("look", "")), ("gucke dich um", ("look", "")), ("Schau dich um", ("look", "")),
    ("sieh dich um", ("look", "")), ("wo bin ich", ("look", "")), ("look", ("look", "")), ("l", ("look", "")),
    ("umgebung", ("look", "")),
    # look_at
    ("untersuche laterne", ("look_at", "laterne")), ("betrachte die laterne", ("look_at", "laterne")),
    ("sieh dir die Laterne an", ("look_at", "laterne")), ("schau dir die laterne an", ("look_at", "laterne")),
    ("guck die laterne an", ("look_at", "laterne")), ("examine laterne", ("look_at", "laterne")),
    ("look at laterne", ("look_at", "laterne")), ("x laterne", ("look_at", "laterne")),
    ("prüfe laterne", ("look_at", "laterne")),
    # take
    ("nimm laterne", ("take", "laterne")), ("nimm dir die laterne", ("take", "laterne")),
    ("nehme die laterne", ("take", "laterne")), ("hebe die laterne auf", ("take", "laterne")),
    ("heb laterne auf", ("take", "laterne")), ("take laterne", ("take", "laterne")),
    ("hole die laterne", ("take", "laterne")), ("schnapp dir die laterne", ("take", "laterne")),
    ("stecke die laterne ein", ("take", "laterne")),
    # drop
    ("lasse laterne", ("drop", "laterne")), ("lass die laterne fallen", ("drop", "laterne")),
    ("lege die laterne ab", ("drop", "laterne")), ("wirf die laterne weg", ("drop", "laterne")),
    ("drop laterne", ("drop", "laterne")),
    # open
    ("öffne tür", ("open", "tür")), ("oeffne die tuer", ("open", "tuer")), ("open tür", ("open", "tür")),
    ("mach die tür auf", ("open", "tür")), ("schließe die tür auf", ("open", "tür")),
    ("schliesse die tuer auf", ("open", "tuer")), ("unlock tür", ("open", "tür")),
    # inventory
    ("inventar", ("inventory", "")), ("i", ("inventory", "")), ("inv", ("inventory", "")),
    ("was habe ich", ("inventory", "")), ("rucksack", ("inventory", "")), ("inventory", ("inventory", "")),
    # map
    ("karte", ("map", "")), ("map", ("map", "")), ("m", ("map", "")), ("zeige karte", ("map", "")),
    # achievements
    ("erfolge", ("achievements", "")), ("achievements", ("achievements", "")), ("zeig erfolge", ("achievements", "")),
    # save/load/slots
    ("speichere", ("save", "")), ("speichere a", ("save", "a")), ("save a", ("save", "a")),
    ("spiel speichern", ("save", "")),
    ("lade", ("load", "")), ("lade a", ("load", "a")), ("load a", ("load", "a")),
    ("spielstaende", ("slots", "")), ("spielstände", ("slots", "")), ("slots", ("slots", "")),
    ("zeige spielstaende", ("slots", "")),
    # help / quit
    ("hilfe", ("help", "")), ("help", ("help", "")), ("?", ("help", "")), ("befehle", ("help", "")),
    ("ende", ("quit", "")), ("quit", ("quit", "")), ("tschüss", ("quit", "")), ("tschuess", ("quit", "")),
    ("exit", ("quit", "")),
]


@pytest.mark.parametrize("text,expected", SYNONYMS)
def test_synonyms(text, expected):
    assert parse(text) == expected


@pytest.mark.parametrize("text,direction", [
    ("runter", "unten"), ("hoch", "oben"), ("sueden", "süden"), ("süden", "süden"), ("nord", "norden"),
    ("n", "norden"), ("s", "süden"), ("o", "osten"), ("w", "westen"), ("h", "oben"), ("u", "unten"),
    ("hinunter", "unten"), ("rauf", "oben"), ("OSTEN", "osten"), ("west", "westen"),
])
def test_bare_direction_is_go(text, direction):
    assert parse(text) == ("go", direction)


@pytest.mark.parametrize("text", ["GEHE NORDEN", "Gehe Norden", "gEhE nOrDeN", "  gehe   norden  ", "gehe\tnorden"])
def test_case_and_whitespace(text):
    assert parse(text) == ("go", "norden")


def test_multiple_spaces_in_multiword_alias():
    assert parse("gucke    dich   um") == ("look", "")
    assert parse("sieh   dir   die   laterne   an") == ("look_at", "laterne")


@pytest.mark.parametrize("text", ["", "   ", "\t", "die", "mit", "der die das"])
def test_empty_or_only_fillers(text):
    assert parse(text) == ("", "")


@pytest.mark.parametrize("text", ["tanze wild", "blubb", "xyzzy laterne", "die laterne nimm"])
def test_unknown_command(text):
    verb, _ = parse(text)
    assert verb == ""


def test_unknown_keeps_rest_as_object():
    assert parse("tanze wild") == ("", "wild")


# Präzedenz: längster Alias vor kürzerem
def test_precedence_schau():
    assert parse("schau dich um") == ("look", "")
    assert parse("schau dir laterne an") == ("look_at", "laterne")
    assert parse("schau laterne") == ("look", "laterne")
    assert parse("schau laterne an") == ("look_at", "laterne")


def test_precedence_nimm_dir():
    assert parse("nimm dir laterne") == ("take", "laterne")
    assert parse("nimm laterne") == ("take", "laterne")


def test_precedence_lass_fallen_vs_lass():
    assert parse("lass laterne fallen") == ("drop", "laterne")
    assert parse("lass laterne") == ("drop", "laterne")


def test_placeholder_needs_object():
    # 'hebe * auf' braucht ein Objekt: 'hebe auf' ist kein take
    assert parse("hebe auf")[0] != "take"


def test_multiword_object_kept():
    assert parse("nimm goldenen schluessel") == ("take", "goldenen schluessel")
    assert parse("untersuche die alte truhe") == ("look_at", "alte truhe")


# Werkzeug
@pytest.mark.parametrize("text,expected", [
    ("öffne die tür mit dem schlüssel", ("open", "tür", "schlüssel")),
    ("oeffne die tuer mit dem schluessel", ("open", "tuer", "schluessel")),
    ("ÖFFNE TÜR MIT SCHLÜSSEL", ("open", "tür", "schlüssel")),
    ("öffne tür", ("open", "tür", "")),
    ("mach die tür mit dem schlüssel auf", ("open", "tür", "schlüssel")),
    ("schließe die tür mit dem schlüssel auf", ("open", "tür", "schlüssel")),
    ("öffne   die   tür   mit   dem   schlüssel", ("open", "tür", "schlüssel")),
    ("öffne die tür mit dem alten schlüssel", ("open", "tür", "alten schlüssel")),
])
def test_with_tool(text, expected):
    assert parse_with_tool(text) == expected


def test_parse_drops_tool_and_command_tuple():
    assert parse("öffne tür mit schlüssel") == ("open", "tür")
    assert parse_command("öffne tür mit schlüssel") == Command("open", "tür", "schlüssel")
    assert parse_command("") == Command("", "", "")


def test_mit_as_first_word_is_not_a_tool_separator():
    assert parse_with_tool("mit schlüssel")[0] == ""


def test_go_with_non_direction_object_is_kept():
    assert parse("gehe tanzen") == ("go", "tanzen")
