// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title PayeeRegistry
/// @notice Confirmation of Payee for stablecoin payments: a merchant claims one
///         human-readable name, and payers confirm that a name and an address
///         belong together before any money moves.
contract PayeeRegistry {
    error NameTaken();
    error AlreadyRegistered();
    error InvalidName();
    error NotRegistered();

    event PayeeRegistered(address indexed account, bytes32 indexed nameHash, string name);
    event PayeeReleased(address indexed account, bytes32 indexed nameHash, string name);

    mapping(bytes32 nameHash => address account) public accountOf;
    mapping(address account => string name) public nameOf;

    /// @notice Claim `name` for the caller. Names are 3-32 chars of [a-z0-9.-].
    function register(string calldata name) external returns (bytes32 nameHash) {
        if (!isValidName(name)) revert InvalidName();
        if (bytes(nameOf[msg.sender]).length != 0) revert AlreadyRegistered();
        nameHash = keccak256(bytes(name));
        if (accountOf[nameHash] != address(0)) revert NameTaken();
        accountOf[nameHash] = msg.sender;
        nameOf[msg.sender] = name;
        emit PayeeRegistered(msg.sender, nameHash, name);
    }

    /// @notice Give the caller's name back. Open invoices from it stop being payable.
    function release() external {
        string memory name = nameOf[msg.sender];
        if (bytes(name).length == 0) revert NotRegistered();
        bytes32 nameHash = keccak256(bytes(name));
        delete accountOf[nameHash];
        delete nameOf[msg.sender];
        emit PayeeReleased(msg.sender, nameHash, name);
    }

    /// @notice True when `name` is registered to exactly `account`.
    function confirm(address account, string calldata name) external view returns (bool) {
        return account != address(0) && accountOf[keccak256(bytes(name))] == account;
    }

    function nameHashOf(address account) public view returns (bytes32) {
        bytes memory name = bytes(nameOf[account]);
        return name.length == 0 ? bytes32(0) : keccak256(name);
    }

    /// @dev Lower-case only, so "Acme" and "acme" cannot be two different payees.
    function isValidName(string calldata name) public pure returns (bool) {
        bytes calldata b = bytes(name);
        if (b.length < 3 || b.length > 32) return false;
        for (uint256 i = 0; i < b.length; i++) {
            bytes1 c = b[i];
            bool ok = (c >= 0x61 && c <= 0x7a) || (c >= 0x30 && c <= 0x39) || c == 0x2d || c == 0x2e;
            if (!ok) return false;
        }
        return true;
    }
}
