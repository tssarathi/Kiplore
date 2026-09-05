import assert from "node:assert/strict";
import { test } from "node:test";
import { parseServerMessage } from "./storyState.ts";

const state = {
  type: "state",
  seq: 1,
  position: 12.5,
  duration: 300,
  paused: false,
  caption: "Once upon a time.",
};

function encode(message: unknown): Uint8Array {
  return new TextEncoder().encode(JSON.stringify(message));
}

test("a well formed state message is accepted", () => {
  assert.deepEqual(parseServerMessage(encode(state)), state);
});

test("a resume acknowledgement carries only its sequence number", () => {
  assert.deepEqual(parseServerMessage(encode({ type: "resume-ack", seq: 3 })), {
    type: "resume-ack",
    seq: 3,
  });
});

test("a malformed message never reaches the player", () => {
  const rejected: unknown[] = [
    { ...state, seq: 0 },
    { ...state, seq: 1.5 },
    { ...state, position: -1 },
    { ...state, position: "12.5" },
    { ...state, duration: Number.NaN },
    { ...state, paused: "false" },
    { ...state, caption: 7 },
    "not an object",
    null,
  ];

  for (const message of rejected) {
    assert.equal(
      parseServerMessage(encode(message)),
      null,
      `accepted ${JSON.stringify(message)}`,
    );
  }
});

test("bytes that are not JSON are rejected rather than thrown", () => {
  assert.equal(parseServerMessage(new Uint8Array([0xff, 0xfe])), null);
});
