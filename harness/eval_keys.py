"""Key matching for eval scoring (S-GEN-041): how a spec key and an agent's key are compared. Stdlib only.

A key part matches after normalising: case folded, `_`, `-` and runs of whitespace read as one space,
outer space dropped. Nothing looser: no stemming, no fuzzy match. A spec may list aliases, other names a
careful writer could fairly use for the same thing; a match on an alias counts.

  norm(text)                                   the normalised form
  name_matches(value, name, aliases)           one part: value names `name` or one of its aliases
  key_matches(entity, attribute, want, alias)  two parts: (entity, attribute) names `want` or an alias pair
"""
import re

_SEP = re.compile(r"[\s_-]+")


def norm(text):
    return _SEP.sub(" ", str(text or "").casefold()).strip()


def name_matches(value, name, aliases=()):
    return bool(norm(value)) and norm(value) in {norm(n) for n in [name, *aliases]}


def key_matches(entity, attribute, want, aliases=()):
    """want and each alias are {entity, attribute}. Both parts must match the same pair."""
    got = (norm(entity), norm(attribute))
    return all(got) and got in {(norm(p["entity"]), norm(p["attribute"])) for p in [want, *aliases]}
