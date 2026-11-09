// Substrate
use sc_chain_spec::{ChainType, Properties};
use sp_consensus_aura::sr25519::AuthorityId as AuraId;
use sp_consensus_grandpa::AuthorityId as GrandpaId;
use sp_core::{sr25519, Pair, Public};
use sp_runtime::traits::{IdentifyAccount, Verify};

use iink_runtime::{
	AccountId, SS58Prefix, Signature, DEVELOPMENT_EVM_CHAIN_ID, LOCAL_EVM_CHAIN_ID, TOKEN_DECIMALS,
	UNIT, WASM_BINARY,
};

pub type ChainSpec = sc_service::GenericChainSpec;

fn get_from_seed<TPublic: Public>(seed: &str) -> <TPublic::Pair as Pair>::Public {
	TPublic::Pair::from_string(&format!("//{seed}"), None)
		.expect("static values are valid; qed")
		.public()
}

type AccountPublic = <Signature as Verify>::Signer;

pub fn get_account_id_from_seed<TPublic: Public>(seed: &str) -> AccountId
where
	AccountPublic: From<<TPublic::Pair as Pair>::Public>,
{
	AccountPublic::from(get_from_seed::<TPublic>(seed)).into_account()
}

fn authority_keys_from_seed(seed: &str) -> (AuraId, GrandpaId) {
	(
		get_from_seed::<AuraId>(seed),
		get_from_seed::<GrandpaId>(seed),
	)
}

fn properties() -> Properties {
	let mut properties = Properties::new();
	properties.insert("tokenSymbol".into(), "IINK".into());
	properties.insert("tokenDecimals".into(), TOKEN_DECIMALS.into());
	properties.insert("ss58Format".into(), SS58Prefix::get().into());
	properties
}

pub fn development_config(enable_manual_seal: bool) -> ChainSpec {
	ChainSpec::builder(WASM_BINARY.expect("WASM not available"), Default::default())
		.with_name("IINK Development")
		.with_id("iink_wallet_dev")
		.with_chain_type(ChainType::Development)
		.with_protocol_id("iink-wallet-dev")
		.with_properties(properties())
		.with_genesis_config_patch(testnet_genesis(
			vec![authority_keys_from_seed("Alice")],
			DEVELOPMENT_EVM_CHAIN_ID,
			enable_manual_seal,
		))
		.build()
}

pub fn local_testnet_config() -> ChainSpec {
	ChainSpec::builder(WASM_BINARY.expect("WASM not available"), Default::default())
		.with_name("IINK Local Testnet")
		.with_id("iink_wallet_local")
		.with_chain_type(ChainType::Local)
		.with_protocol_id("iink-wallet-local")
		.with_properties(properties())
		.with_genesis_config_patch(testnet_genesis(
			vec![
				authority_keys_from_seed("Alice"),
				authority_keys_from_seed("Bob"),
			],
			LOCAL_EVM_CHAIN_ID,
			false,
		))
		.build()
}

fn testnet_genesis(
	initial_authorities: Vec<(AuraId, GrandpaId)>,
	chain_id: u64,
	enable_manual_seal: bool,
) -> serde_json::Value {
	let alice = get_account_id_from_seed::<sr25519::Public>("Alice");
	let bob = get_account_id_from_seed::<sr25519::Public>("Bob");
	serde_json::json!({
		"sudo": { "key": alice.clone() },
		"balances": { "balances": [(alice, 1_000_000 * UNIT), (bob, 1_000_000 * UNIT)] },
		"aura": { "authorities": initial_authorities.iter().map(|x| x.0.clone()).collect::<Vec<_>>() },
		"grandpa": { "authorities": initial_authorities.iter().map(|x| (x.1.clone(), 1)).collect::<Vec<_>>() },
		"evmChainId": { "chainId": chain_id },
		"manualSeal": { "enable": enable_manual_seal }
	})
}
