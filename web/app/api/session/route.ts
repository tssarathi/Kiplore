import { AccessToken, RoomConfiguration } from "livekit-server-sdk";
import { getStory, getVoices } from "@/lib/content";

/** Mint a LiveKit token for one story session. */
export async function POST(request: Request) {
  // development only: the token grants publish rights on a live session
  if (process.env.NODE_ENV !== "development") {
    return Response.json({ error: "not available" }, { status: 403 });
  }

  const url = process.env.LIVEKIT_URL;
  const key = process.env.LIVEKIT_API_KEY;
  const secret = process.env.LIVEKIT_API_SECRET;
  if (!url || !key || !secret) {
    return Response.json({ error: "server not configured" }, { status: 500 });
  }

  // checked here, because the choice is about to be signed into a token
  const { collection, storyId, voiceId } = await request.json();
  const story = await getStory(collection, storyId);
  const voices = await getVoices();
  if (!story || !voices.some((voice) => voice.id === voiceId)) {
    return Response.json({ error: "no such story" }, { status: 404 });
  }

  const session = crypto.randomUUID().slice(0, 8);

  // the agent reads this on join: which story, which voice, no second request
  const token = new AccessToken(key, secret, {
    identity: `kid-${session}`,
    ttl: "15m",
    metadata: JSON.stringify({ collection, storyId, voiceId }),
  });

  token.roomConfig = new RoomConfiguration({ departureTimeout: 90 });

  // a fresh room per session, so two children never share one telling
  token.addGrant({
    roomJoin: true,
    room: `story-${storyId}-${session}`,
    canPublish: true,
    canSubscribe: true,
  });

  return Response.json({ token: await token.toJwt(), url });
}
