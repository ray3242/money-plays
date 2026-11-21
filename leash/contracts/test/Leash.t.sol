// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Leash} from "../src/Leash.sol";
import {PayeeRegistry} from "../src/PayeeRegistry.sol";

contract MockUSD is ERC20("Test USD", "tUSD8") {
    function decimals() public pure override returns (uint8) {
        return 6;
    }

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

contract LeashTest is Test {
    MockUSD token;
    PayeeRegistry registry;
    Leash leash;

    address owner = makeAddr("owner");
    address merchant = makeAddr("merchant");
    address attacker = makeAddr("attacker");
    address relayer = makeAddr("relayer");
    uint256 agentKey = 0xA6E47;
    address agent;
    uint256 leashId;

    uint128 constant USD = 1e6;

    function setUp() public {
        vm.warp(1_800_000_000);
        token = new MockUSD();
        registry = new PayeeRegistry();
        leash = new Leash(token, registry);
        agent = vm.addr(agentKey);

        token.mint(owner, 1000 * USD);
        vm.startPrank(owner);
        token.approve(address(leash), type(uint256).max);
        leash.deposit(500 * USD);
        string[] memory none = new string[](0);
        leashId = leash.createLeash(agent, 100 * USD, 1 days, 40 * USD, uint64(block.timestamp + 30 days), none);
        vm.stopPrank();

        vm.prank(merchant);
        registry.register("acme-cloud");
        vm.prank(attacker);
        registry.register("acme-c1oud");
    }

    function _invoice(address from, uint128 amount) internal returns (uint256 id) {
        vm.prank(from);
        id = leash.createInvoice(owner, amount, 0, "hosting");
    }

    function _intent(uint256 lid, uint256 invoiceId) internal view returns (Leash.PaymentIntent memory i) {
        Leash.Invoice memory inv = leash.getInvoice(invoiceId);
        i = Leash.PaymentIntent(lid, invoiceId, inv.payee, inv.payeeNameHash, inv.amount, block.timestamp + 1 hours);
    }

    function _sign(uint256 key, Leash.PaymentIntent memory i) internal view returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, leash.hashIntent(i));
        return abi.encodePacked(r, s, v);
    }

    function _expectRefused(Leash.PaymentIntent memory i, bytes memory sig, Leash.Check reason) internal {
        assertEq(uint8(leash.preview(i, sig)), uint8(reason), "preview reason");
        vm.expectRevert(abi.encodeWithSelector(Leash.Refused.selector, reason));
        leash.payWithIntent(i, sig);
    }

    function test_agentPaysInvoice_relayedByAnyone() public {
        uint256 id = _invoice(merchant, 25 * USD);
        Leash.PaymentIntent memory i = _intent(leashId, id);
        bytes memory sig = _sign(agentKey, i);
        assertEq(uint8(leash.preview(i, sig)), uint8(Leash.Check.Ok));

        vm.expectEmit(true, true, true, true);
        emit Leash.InvoicePaid(id, leashId, merchant, owner, 25 * USD, relayer);
        vm.prank(relayer);
        leash.payWithIntent(i, sig);

        assertEq(token.balanceOf(merchant), 25 * USD);
        assertEq(leash.vaultOf(owner), 475 * USD);
        assertEq(leash.remainingBudget(leashId), 75 * USD);
        Leash.Invoice memory inv = leash.getInvoice(id);
        assertEq(uint8(inv.status), uint8(Leash.InvoiceStatus.Paid));
        assertEq(inv.paidByLeash, leashId);
        assertEq(token.balanceOf(agent), 0);
        assertEq(agent.balance, 0, "agent key never needs gas");
    }

    function test_replayIsRefused() public {
        uint256 id = _invoice(merchant, 25 * USD);
        Leash.PaymentIntent memory i = _intent(leashId, id);
        bytes memory sig = _sign(agentKey, i);
        leash.payWithIntent(i, sig);
        _expectRefused(i, sig, Leash.Check.InvoiceNotOpen);
        assertEq(token.balanceOf(merchant), 25 * USD);
    }

    function test_overPaymentCapRefused_thenOwnerApproves() public {
        uint256 id = _invoice(merchant, 41 * USD);
        Leash.PaymentIntent memory i = _intent(leashId, id);
        _expectRefused(i, _sign(agentKey, i), Leash.Check.OverPaymentCap);

        vm.prank(owner);
        leash.payAsOwner(id);
        assertEq(token.balanceOf(merchant), 41 * USD);
        assertEq(leash.getInvoice(id).paidByLeash, 0);
        assertEq(leash.remainingBudget(leashId), 100 * USD, "owner payments do not use the agent budget");
    }

    function test_budgetPerPeriod_andReset() public {
        for (uint256 n = 0; n < 2; n++) {
            uint256 id = _invoice(merchant, 40 * USD);
            Leash.PaymentIntent memory i = _intent(leashId, id);
            leash.payWithIntent(i, _sign(agentKey, i));
        }
        uint256 third = _invoice(merchant, 30 * USD);
        Leash.PaymentIntent memory i3 = _intent(leashId, third);
        _expectRefused(i3, _sign(agentKey, i3), Leash.Check.OverBudget);

        vm.warp(block.timestamp + 1 days);
        assertEq(leash.remainingBudget(leashId), 100 * USD);
        i3 = _intent(leashId, third);
        leash.payWithIntent(i3, _sign(agentKey, i3));
        assertEq(leash.remainingBudget(leashId), 70 * USD);
        assertEq(leash.getLeash(leashId).totalSpent, 110 * USD);
    }

    function test_lifetimeBudgetNeverResets() public {
        string[] memory none = new string[](0);
        vm.prank(owner);
        uint256 lid = leash.createLeash(agent, 30 * USD, 0, 30 * USD, uint64(block.timestamp + 365 days), none);
        uint256 a = _invoice(merchant, 30 * USD);
        Leash.PaymentIntent memory i = _intent(lid, a);
        leash.payWithIntent(i, _sign(agentKey, i));
        vm.warp(block.timestamp + 100 days);
        uint256 b = _invoice(merchant, 1 * USD);
        i = _intent(lid, b);
        _expectRefused(i, _sign(agentKey, i), Leash.Check.OverBudget);
    }

    function test_revokeKillsSignedIntents() public {
        uint256 id = _invoice(merchant, 10 * USD);
        Leash.PaymentIntent memory i = _intent(leashId, id);
        bytes memory sig = _sign(agentKey, i);
        vm.prank(owner);
        leash.revoke(leashId);
        _expectRefused(i, sig, Leash.Check.LeashRevoked);
    }

    function test_onlyOwnerRevokes() public {
        vm.prank(attacker);
        vm.expectRevert(Leash.NotOwner.selector);
        leash.revoke(leashId);
    }

    function test_expiryRefused() public {
        uint256 id = _invoice(merchant, 10 * USD);
        vm.warp(block.timestamp + 30 days);
        Leash.PaymentIntent memory i = _intent(leashId, id);
        _expectRefused(i, _sign(agentKey, i), Leash.Check.LeashExpired);
    }

    function test_intentDeadlineRefused() public {
        uint256 id = _invoice(merchant, 10 * USD);
        Leash.PaymentIntent memory i = _intent(leashId, id);
        bytes memory sig = _sign(agentKey, i);
        vm.warp(block.timestamp + 2 hours);
        _expectRefused(i, sig, Leash.Check.IntentExpired);
    }

    function test_wrongSignerRefused() public {
        uint256 id = _invoice(merchant, 10 * USD);
        Leash.PaymentIntent memory i = _intent(leashId, id);
        _expectRefused(i, _sign(0xBAD, i), Leash.Check.BadSignature);
        _expectRefused(i, hex"1234", Leash.Check.BadSignature);
    }

    function test_tamperedIntentRefused() public {
        uint256 id = _invoice(merchant, 10 * USD);
        Leash.PaymentIntent memory i = _intent(leashId, id);
        bytes memory sig = _sign(agentKey, i);
        i.payee = attacker;
        _expectRefused(i, sig, Leash.Check.BadSignature);
    }

    function test_allowlistBlocksLookalikePayee() public {
        string[] memory allowed = new string[](1);
        allowed[0] = "acme-cloud";
        vm.prank(owner);
        uint256 lid = leash.createLeash(agent, 100 * USD, 0, 50 * USD, uint64(block.timestamp + 1 days), allowed);

        uint256 fake = _invoice(attacker, 10 * USD);
        Leash.PaymentIntent memory i = _intent(lid, fake);
        _expectRefused(i, _sign(agentKey, i), Leash.Check.PayeeNotAllowed);

        uint256 real = _invoice(merchant, 10 * USD);
        i = _intent(lid, real);
        leash.payWithIntent(i, _sign(agentKey, i));

        assertEq(leash.allowlistOf(lid).length, 1);
        vm.prank(owner);
        leash.setPayeeAllowed(lid, "acme-cloud", false);
        assertEq(leash.allowlistOf(lid).length, 0);
        uint256 real2 = _invoice(merchant, 10 * USD);
        i = _intent(lid, real2);
        _expectRefused(i, _sign(agentKey, i), Leash.Check.PayeeNotAllowed);
    }

    function test_confirmationOfPayee_nameMustMatchAddress() public {
        // The agent thinks it is paying "acme-cloud", but the invoice came from the lookalike.
        uint256 fake = _invoice(attacker, 10 * USD);
        Leash.PaymentIntent memory i = _intent(leashId, fake);
        i.payeeNameHash = keccak256("acme-cloud");
        _expectRefused(i, _sign(agentKey, i), Leash.Check.PayeeMismatch);
    }

    function test_releasedNameStopsPayment() public {
        uint256 id = _invoice(merchant, 10 * USD);
        vm.prank(merchant);
        registry.release();
        Leash.PaymentIntent memory i = _intent(leashId, id);
        _expectRefused(i, _sign(agentKey, i), Leash.Check.PayeeMismatch);
        vm.prank(owner);
        vm.expectRevert(abi.encodeWithSelector(Leash.Refused.selector, Leash.Check.PayeeMismatch));
        leash.payAsOwner(id);
    }

    function test_amountMismatchRefused() public {
        uint256 id = _invoice(merchant, 10 * USD);
        Leash.PaymentIntent memory i = _intent(leashId, id);
        i.amount = 9 * USD;
        _expectRefused(i, _sign(agentKey, i), Leash.Check.AmountMismatch);
    }

    function test_cannotSpendAnotherOwnersVault() public {
        address other = makeAddr("other");
        vm.prank(merchant);
        uint256 id = leash.createInvoice(other, 10 * USD, 0, "x");
        Leash.PaymentIntent memory i = _intent(leashId, id);
        _expectRefused(i, _sign(agentKey, i), Leash.Check.WrongPayer);
    }

    function test_overdueAndCancelledRefused() public {
        vm.prank(merchant);
        uint256 id = leash.createInvoice(owner, 10 * USD, uint64(block.timestamp + 1 hours), "due soon");
        vm.warp(block.timestamp + 2 hours);
        Leash.PaymentIntent memory i = _intent(leashId, id);
        _expectRefused(i, _sign(agentKey, i), Leash.Check.InvoiceOverdue);

        uint256 id2 = _invoice(merchant, 10 * USD);
        vm.prank(attacker);
        vm.expectRevert(Leash.NotPayee.selector);
        leash.cancelInvoice(id2);
        vm.prank(merchant);
        leash.cancelInvoice(id2);
        i = _intent(leashId, id2);
        _expectRefused(i, _sign(agentKey, i), Leash.Check.InvoiceNotOpen);
    }

    function test_insufficientVaultRefused() public {
        vm.prank(owner);
        leash.withdraw(495 * USD);
        uint256 id = _invoice(merchant, 10 * USD);
        Leash.PaymentIntent memory i = _intent(leashId, id);
        _expectRefused(i, _sign(agentKey, i), Leash.Check.InsufficientVault);
    }

    function test_unregisteredMerchantCannotInvoice() public {
        vm.prank(relayer);
        vm.expectRevert(Leash.PayeeNotRegistered.selector);
        leash.createInvoice(owner, 1 * USD, 0, "x");
    }

    function test_withdrawOnlyOwnBalance() public {
        vm.prank(attacker);
        vm.expectRevert();
        leash.withdraw(1);
        vm.prank(owner);
        leash.withdraw(500 * USD);
        assertEq(token.balanceOf(owner), 1000 * USD);
    }

    function test_invalidLeashParams() public {
        string[] memory none = new string[](0);
        vm.startPrank(owner);
        vm.expectRevert(Leash.InvalidLeash.selector);
        leash.createLeash(agent, 0, 0, 1, uint64(block.timestamp + 1), none);
        vm.expectRevert(Leash.InvalidLeash.selector);
        leash.createLeash(agent, 1, 0, 1, uint64(block.timestamp), none);
        vm.expectRevert(Leash.ZeroAddress.selector);
        leash.createLeash(address(0), 1, 0, 1, uint64(block.timestamp + 1), none);
        vm.stopPrank();
    }

    function test_registryRules() public {
        assertTrue(registry.confirm(merchant, "acme-cloud"));
        assertFalse(registry.confirm(attacker, "acme-cloud"));
        vm.startPrank(relayer);
        vm.expectRevert(PayeeRegistry.NameTaken.selector);
        registry.register("acme-cloud");
        vm.expectRevert(PayeeRegistry.InvalidName.selector);
        registry.register("Acme-Cloud");
        vm.expectRevert(PayeeRegistry.InvalidName.selector);
        registry.register("ab");
        registry.register("relay.co");
        vm.expectRevert(PayeeRegistry.AlreadyRegistered.selector);
        registry.register("relay2");
        vm.stopPrank();
    }

    /// Whatever the agent signs, a leash never pays out more than its budget in one period,
    /// and the contract always holds exactly what the vaults say.
    function testFuzz_neverExceedsBudget(uint128[8] memory amounts, uint128 budget, uint128 cap) public {
        budget = uint128(bound(budget, 1, 400 * USD));
        cap = uint128(bound(cap, 1, 400 * USD));
        string[] memory none = new string[](0);
        vm.prank(owner);
        uint256 lid = leash.createLeash(agent, budget, 1 days, cap, uint64(block.timestamp + 1 days), none);

        uint256 paid;
        for (uint256 n = 0; n < amounts.length; n++) {
            uint128 amount = uint128(bound(amounts[n], 1, 450 * USD));
            uint256 id = _invoice(merchant, amount);
            Leash.PaymentIntent memory i = _intent(lid, id);
            bytes memory sig = _sign(agentKey, i);
            if (leash.preview(i, sig) == Leash.Check.Ok) {
                leash.payWithIntent(i, sig);
                paid += amount;
                assertLe(amount, cap);
            } else {
                vm.expectRevert();
                leash.payWithIntent(i, sig);
            }
        }
        assertLe(paid, budget);
        assertEq(token.balanceOf(merchant), paid);
        assertEq(token.balanceOf(address(leash)), leash.vaultOf(owner));
        assertEq(leash.vaultOf(owner), 500 * USD - paid);
    }
}
