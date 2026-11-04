// SPDX-License-Identifier: Unlicense
pragma solidity 0.8.30;

contract Counter {
    uint256 public value = 7;

    function increment() external {
        value += 1;
    }
}
