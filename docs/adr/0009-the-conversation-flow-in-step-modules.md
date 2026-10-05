# ADR 0009 · The conversation flow in step modules

**Date:** 2026-10-05 · **Status:** accepted

## Context

The conversation's state machine lived in one module, `vera/core/flow.py`: 1,281 lines and one class with 69 methods. Every change to a step meant reading the whole file, and a review could not take one group of steps at a time.

## Decision

1. **`vera/core/flow.py` keeps the public face and the pipeline of a turn.** `Conversation` exposes `start`, `reply` and `history`, rebuilds the state from the log, reads the message and dispatches it to the open step, then validates and records the reply.
2. **The steps live in `vera/core/steps/`, one module per group:**

   | Module | Steps |
   |---|---|
   | `safety.py` | What wins over any step: a person, a threat, the regulator, an injection and the turn limit |
   | `person.py` | The offer before a transfer, the check of an unsure reading and the way back to the open question |
   | `claim.py` | The opening, the claim and the key questions of a scam |
   | `lost_card.py` | A lost or stolen card protected first, then its movements reviewed |
   | `charges.py` | The search, the choice, how the charge was bought, the card and the sweep |
   | `actions.py` | The block and the registration on a yes, each read back, and the closing of a case |
   | `handoff.py` | The transfer note, a failed tool and the fraud alert |
   | `base.py` | `FlowSupport`: the dependencies and the helpers every step shares, and the `Turn` being built |

3. **Each group is a mixin over `FlowSupport`, and `Conversation` composes them.** A step that leads to another group's step, such as the sweep leading to a proposed registration, calls it on the conversation.

## Rejected alternatives

| Alternative | Reason |
|---|---|
| One class per step, with a shared context object | Steps chain across groups (search, choice, clarification, sweep, signals, proposal), so each object would need references to the others, and every step would have to be rewritten. That is a rewrite, not a move, on the day of the delivery |
| Keep one module | Readable only as a whole; a group of steps could not be reviewed or changed alone |

## Evidence

The methods moved unchanged: a script cut each one from the syntax tree of the old module, so no logic was retyped. Only the module helpers lost their leading underscore, since other modules now import them.

| Check | Result |
|---|---|
| Full Python suite | Green. One test patched `build_transfer` where the flow used it, and now patches it in `steps/handoff.py` |
| The 294 runs of the development set, with the rules and with the classifier | Every request, reply, option, state, grade and recorded event is byte for byte the same as before (SHA-256 `94eb2af4…`), with volatile ids, tokens and times replaced in order of appearance |
| Positive control of that comparison | One word changed in one Spanish template changes the hash |
| Architecture tests | `vera/core/steps` falls under the domain rule: it imports no adapter, store or model |

## Consequences

- `vera/core/flow.py` has 207 lines, and no step module has more than 320.
- A group of steps reads and changes on its own, with its rule ids in its docstrings.
- The mixins share the state of `FlowSupport`. A step module may call a step of another group only through the conversation, never by importing the other module.
