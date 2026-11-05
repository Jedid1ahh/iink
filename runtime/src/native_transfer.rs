use fp_evm::{
	ExitRevert, ExitSucceed, Precompile, PrecompileFailure, PrecompileHandle, PrecompileOutput,
	PrecompileResult,
};
use frame_support::dispatch::GetDispatchInfo;
use pallet_evm::{AddressMapping, GasWeightMapping};
use sp_core::U256;
use sp_runtime::traits::Dispatchable;

use crate::{AccountId, BalancesCall, Runtime, RuntimeCall};

// transferToNative(bytes32,uint128)
const SELECTOR: [u8; 4] = [0xb1, 0xb0, 0x35, 0x9b];

// The transfer can create one System.Account entry. Charge its key and value size
// conservatively on every call, including transfers to existing accounts.
const ACCOUNT_STORAGE_GROWTH: u64 = 256;

pub struct NativeTransfer;

impl Precompile for NativeTransfer {
	fn execute(handle: &mut impl PrecompileHandle) -> PrecompileResult {
		let context = handle.context();
		if handle.is_static()
			|| context.address != handle.code_address()
			|| context.apparent_value != U256::zero()
		{
			return Err(revert());
		}

		let input = handle.input();
		if input.len() != 68 || input[..4] != SELECTOR || input[36..52] != [0; 16] {
			return Err(revert());
		}
		let dest: [u8; 32] = input[4..36].try_into().map_err(|_| revert())?;
		let amount = u128::from_be_bytes(input[52..68].try_into().map_err(|_| revert())?);
		if dest == [0; 32] || amount == 0 {
			return Err(revert());
		}

		let source =
			<Runtime as pallet_evm::Config>::AddressMapping::into_account_id(context.caller);
		let dest = AccountId::from(dest);
		if dest == source {
			return Err(revert());
		}
		let call = RuntimeCall::Balances(BalancesCall::transfer_keep_alive {
			dest: dest.into(),
			value: amount,
		});
		let weight = call.get_dispatch_info().total_weight();
		handle.record_cost(
			<Runtime as pallet_evm::Config>::GasWeightMapping::weight_to_gas(weight),
		)?;
		handle.record_external_cost(
			Some(weight.ref_time()),
			Some(weight.proof_size()),
			Some(ACCOUNT_STORAGE_GROWTH),
		)?;
		call.dispatch(frame_system::RawOrigin::Signed(source).into())
			.map_err(|_| revert())?;

		Ok(PrecompileOutput {
			exit_status: ExitSucceed::Returned,
			output: Default::default(),
		})
	}
}

fn revert() -> PrecompileFailure {
	PrecompileFailure::Revert {
		exit_status: ExitRevert::Reverted,
		output: Default::default(),
	}
}
