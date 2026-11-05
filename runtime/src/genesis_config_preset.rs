use crate::{
	AccountId, BalancesConfig, EVMChainIdConfig, RuntimeGenesisConfig, SudoConfig,
	DEVELOPMENT_EVM_CHAIN_ID, UNIT,
};
use hex_literal::hex;
use sp_genesis_builder::PresetId;
use sp_std::prelude::*;

/// Native Alice is the sole funded account in the runtime's development preset.
pub fn development() -> serde_json::Value {
	let alice = AccountId::from(hex!(
		"d43593c715fdd31c61141abd04a99fd6822c8558854ccde39a5684e7a56da27d"
	));
	let config = RuntimeGenesisConfig {
		balances: BalancesConfig {
			balances: vec![(alice.clone(), 1_000_000 * UNIT)],
			..Default::default()
		},
		evm_chain_id: EVMChainIdConfig {
			chain_id: DEVELOPMENT_EVM_CHAIN_ID,
			..Default::default()
		},
		sudo: SudoConfig { key: Some(alice) },
		..Default::default()
	};
	serde_json::to_value(config).expect("Could not build genesis config.")
}

pub fn get_preset(id: &PresetId) -> Option<Vec<u8>> {
	match id.as_str() {
		sp_genesis_builder::DEV_RUNTIME_PRESET => {
			Some(serde_json::to_vec(&development()).expect("Could not serialize genesis config."))
		}
		_ => None,
	}
}
