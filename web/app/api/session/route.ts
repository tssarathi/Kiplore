import { AccessToken } from "livekit-server-sdk";

export async function POST(request: Request) {
  const url = process.env.LIVEKIT_URL;
  const key = process.env.LIVEKIT_API_KEY;
  const secret = process.env.LIVEKIT_API_SECRET;
  if (!url || !key || !secret) {
    return Response.json({ error: "server not configured" }, { status: 500 });
  }

  const { collection, storyId } = await request.json();
  const session = crypto.randomUUID().slice(0, 8);

  const token = new AccessToken(key, secret, {
    identity: `kid-${session}`,
    ttl: "15m",
    metadata: JSON.stringify({ collection, storyId }),
  });

  token.addGrant({
    roomJoin: true,
    room: `story-${storyId}-${session}`,
    canPublish: true,
    canSubscribe: true,
  });

  return Response.json({ token: await token.toJwt(), url });
}
