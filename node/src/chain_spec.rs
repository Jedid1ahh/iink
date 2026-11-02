use sc_service::ChainType;
use solochain_template_runtime::WASM_BINARY;

/// Specialized `ChainSpec`. This is a specialization of the general Substrate ChainSpec type.
pub type ChainSpec = sc_service::GenericChainSpec;

/// Display metadata for test tokens; this does not define production economics.
fn iink_properties() -> sc_service::Properties {
	let mut properties = sc_service::Properties::new();
	properties.insert("tokenSymbol".into(), "IINK".into());
	// Matches the inherited runtime UNIT = 1_000_000_000_000.
	properties.insert("tokenDecimals".into(), 12.into());
	properties
}

pub fn development_chain_spec() -> Result<ChainSpec, String> {
	Ok(ChainSpec::builder(
		WASM_BINARY.ok_or_else(|| "Development wasm not available".to_string())?,
		None,
	)
	.with_name("IINK Development")
	.with_id("iink_dev")
	.with_properties(iink_properties())
	.with_protocol_id("iink-dev")
	.with_chain_type(ChainType::Development)
	.with_genesis_config_preset_name(sp_genesis_builder::DEV_RUNTIME_PRESET)
	.build())
}

pub fn local_chain_spec() -> Result<ChainSpec, String> {
	Ok(ChainSpec::builder(
		WASM_BINARY.ok_or_else(|| "Development wasm not available".to_string())?,
		None,
	)
	.with_name("IINK Local Testnet")
	.with_id("iink_local")
	.with_properties(iink_properties())
	.with_protocol_id("iink-local")
	.with_chain_type(ChainType::Local)
	.with_genesis_config_preset_name(sp_genesis_builder::LOCAL_TESTNET_RUNTIME_PRESET)
	.build())
}
