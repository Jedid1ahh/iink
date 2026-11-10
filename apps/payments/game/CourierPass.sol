// SPDX-License-Identifier: Unlicense
pragma solidity 0.8.30;

contract CourierPass {
    uint256 public constant PRICE = 0.1 ether;
    address payable public treasury;
    mapping(address => bool) public ownsPass;

    event PassPurchased(address indexed buyer);

    error IncorrectPrice();
    error PassAlreadyOwned();
    error PayoutFailed();

    constructor() {
        treasury = payable(msg.sender);
    }

    function buy() external payable {
        if (msg.value != PRICE) revert IncorrectPrice();
        if (ownsPass[msg.sender]) revert PassAlreadyOwned();

        ownsPass[msg.sender] = true;
        (bool paid,) = treasury.call{value: msg.value}("");
        if (!paid) revert PayoutFailed();
        emit PassPurchased(msg.sender);
    }
}
