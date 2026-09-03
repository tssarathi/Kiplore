import { AccessToken, RoomConfiguration } from "livekit-server-sdk";
import { getStory, getVoices } from "@/lib/content";

export async function POST(request: Request) {
  if (process.env.NODE_ENV !== "development") {
    return Response.json({ error: "not available" }, { status: 403 });
  }

  const url = process.env.LIVEKIT_URL;
  const key = process.env.LIVEKIT_API_KEY;
  const secret = process.env.LIVEKIT_API_SECRET;
  if (!url || !key || !secret) {
    return Response.json({ error: "server not configured" }, { status: 500 });
  }

  const { collection, storyId, voiceId } = await request.json();
  const story = await getStory(collection, storyId);
  const voices = await getVoices();
  if (!story || !voices.some((voice) => voice.id === voiceId)) {
    return Response.json({ error: "no such story" }, { status: 404 });
  }

  const session = crypto.randomUUID().slice(0, 8);

  const token = new AccessToken(key, secret, {
    identity: `kid-${session}`,
    ttl: "15m",
    metadata: JSON.stringify({ collection, storyId, voiceId }),
  });

  token.roomConfig = new RoomConfiguration({ departureTimeout: 90 });

  token.addGrant({
    roomJoin: true,
    room: `story-${storyId}-${session}`,
    canPublish: true,
    canSubscribe: true,
  });

  return Response.json({ token: await token.toJwt(), url });
}
