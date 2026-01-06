import { SuiClient } from "@mysten/sui/client";

const RPC_URL = process.env.SUI_RPC_URL || "https://fullnode.mainnet.sui.io";

async function fetchReserveEvents() {
  const suiClient = new SuiClient({ url: RPC_URL });

  // Query the specific Move event type for reserve data updates
  const eventType = "0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::suilend::ApiReserveAssetDataEvent";

  const result = await suiClient.queryEvents({
    query: { MoveEventType: eventType },
    // use descending_order: true to get most recent first if supported
    descending_order: true
  });

  return result.data;
}

fetchReserveEvents()
  .then(events => {
    console.log("Found events:", events.length);
    console.log(events);
  })
  .catch(console.error);
