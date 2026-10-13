import { ethers } from "ethers";

// Vercyra Coin — Ethereum connection
const ALCHEMY_API_KEY = import.meta.env.VITE_ALCHEMY_API_KEY;

const provider = ALCHEMY_API_KEY
	? new ethers.JsonRpcProvider(
			`https://eth-sepolia.g.alchemy.com/v2/${ALCHEMY_API_KEY}`
		)
	: null;

export async function checkBlockchainConnection() {
	if (!provider) {
		throw new Error("Alchemy API key is not configured.");
	}

	const network = await provider.getNetwork();
	const blockNumber = await provider.getBlockNumber();

	return {
		network: network.name,
		chainId: Number(network.chainId),
		blockNumber,
	};
    VITE_ALCHEMY_API_KEY=YOUR_API_KEY_HERE
}
