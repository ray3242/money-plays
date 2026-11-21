// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Leash} from "../src/Leash.sol";
import {PayeeRegistry} from "../src/PayeeRegistry.sol";

/// forge script script/Deploy.s.sol --rpc-url https://rpc-test.qday.info --broadcast --legacy
contract Deploy is Script {
    // tUSD8 on QDay Aevum Testnet (chain 44005), from https://qday.io/official-links
    address constant TUSD8 = 0x456569838f1d43009A91ebA4263147Afd7233483;

    function run() external {
        address token = vm.envOr("TOKEN", TUSD8);
        vm.startBroadcast();
        PayeeRegistry registry = new PayeeRegistry();
        Leash leash = new Leash(IERC20(token), registry);
        vm.stopBroadcast();
        console.log("PayeeRegistry", address(registry));
        console.log("Leash", address(leash));
    }
}
