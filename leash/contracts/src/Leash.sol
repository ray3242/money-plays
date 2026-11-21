// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {PayeeRegistry} from "./PayeeRegistry.sol";

/// @title Leash
/// @notice Lets a business hand invoice payments to an AI agent without handing it
///         the money. The owner funds a vault and gives an agent key a leash: a
///         budget per period, a cap per payment, an expiry and a payee allowlist.
///         The agent key holds no funds and no gas. It only signs EIP-712 payment
///         intents, which anyone (normally the merchant being paid) can submit.
///         Every rule is enforced here, on-chain, so a tricked or broken agent
///         cannot spend outside its leash.
contract Leash is EIP712, ReentrancyGuard {
    using SafeERC20 for IERC20;

    enum InvoiceStatus {
        None,
        Open,
        Paid,
        Cancelled
    }

    /// @notice Why a payment would be refused. `Ok` means it would go through.
    enum Check {
        Ok,
        LeashNotFound,
        LeashRevoked,
        LeashExpired,
        IntentExpired,
        BadSignature,
        InvoiceNotOpen,
        InvoiceOverdue,
        WrongPayer,
        AmountMismatch,
        PayeeMismatch,
        PayeeNotAllowed,
        OverPaymentCap,
        OverBudget,
        InsufficientVault
    }

    struct LeashData {
        address owner;
        address agent;
        uint64 expiry;
        uint64 period; // seconds; 0 = the budget is for the leash's whole life
        uint64 periodStart;
        bool revoked;
        bool allowlistOnly;
        uint128 budget; // per period
        uint128 spentInPeriod;
        uint128 perPaymentCap;
        uint128 totalSpent;
    }

    struct Invoice {
        address payee;
        address payer;
        uint128 amount;
        uint64 dueBy; // 0 = no due date
        uint64 paidAt;
        InvoiceStatus status;
        bytes32 payeeNameHash;
        uint256 paidByLeash; // 0 = paid by the owner directly
        string memo;
    }

    struct PaymentIntent {
        uint256 leashId;
        uint256 invoiceId;
        address payee;
        bytes32 payeeNameHash;
        uint256 amount;
        uint256 deadline;
    }

    bytes32 public constant INTENT_TYPEHASH = keccak256(
        "PaymentIntent(uint256 leashId,uint256 invoiceId,address payee,bytes32 payeeNameHash,uint256 amount,uint256 deadline)"
    );

    IERC20 public immutable token;
    PayeeRegistry public immutable registry;

    mapping(address owner => uint256) public vaultOf;
    mapping(uint256 id => LeashData) internal _leashes;
    mapping(uint256 id => Invoice) internal _invoices;
    mapping(uint256 leashId => mapping(bytes32 nameHash => bool)) public payeeAllowed;
    mapping(uint256 leashId => string[]) internal _allowlistNames;
    mapping(uint256 leashId => mapping(bytes32 nameHash => bool)) internal _everListed;
    mapping(address owner => uint256[]) internal _leashesOf;
    mapping(address payer => uint256[]) internal _invoicesFor;
    mapping(address payee => uint256[]) internal _invoicesBy;
    uint256 public leashCount;
    uint256 public invoiceCount;

    event Deposited(address indexed owner, uint256 amount);
    event Withdrawn(address indexed owner, uint256 amount);
    event LeashCreated(
        uint256 indexed leashId,
        address indexed owner,
        address indexed agent,
        uint256 budget,
        uint256 period,
        uint256 perPaymentCap,
        uint256 expiry,
        bool allowlistOnly
    );
    event PayeeAllowlisted(uint256 indexed leashId, bytes32 indexed nameHash, string name, bool allowed);
    event LeashRevoked(uint256 indexed leashId);
    event InvoiceCreated(
        uint256 indexed invoiceId,
        address indexed payee,
        address indexed payer,
        uint256 amount,
        uint256 dueBy,
        bytes32 payeeNameHash,
        string memo
    );
    event InvoiceCancelled(uint256 indexed invoiceId);
    /// @notice The receipt. `leashId` is 0 when the owner paid directly.
    event InvoicePaid(
        uint256 indexed invoiceId,
        uint256 indexed leashId,
        address indexed payee,
        address payer,
        uint256 amount,
        address submittedBy
    );

    error ZeroAmount();
    error ZeroAddress();
    error NotOwner();
    error NotPayee();
    error PayeeNotRegistered();
    error InvalidLeash();
    error Refused(Check reason);

    constructor(IERC20 token_, PayeeRegistry registry_) EIP712("Leash", "1") {
        if (address(token_) == address(0) || address(registry_) == address(0)) revert ZeroAddress();
        token = token_;
        registry = registry_;
    }

    // ───────────────────────────── Owner: vault ─────────────────────────────

    function deposit(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();
        vaultOf[msg.sender] += amount;
        token.safeTransferFrom(msg.sender, address(this), amount);
        emit Deposited(msg.sender, amount);
    }

    function withdraw(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();
        vaultOf[msg.sender] -= amount; // reverts on underflow
        token.safeTransfer(msg.sender, amount);
        emit Withdrawn(msg.sender, amount);
    }

    // ───────────────────────────── Owner: leashes ───────────────────────────

    /// @param agent Key the agent signs with. It never needs funds or gas.
    /// @param budget Most the agent may spend per `period`.
    /// @param period Seconds per budget window; 0 makes `budget` a lifetime cap.
    /// @param perPaymentCap Most a single payment may be.
    /// @param expiry Unix time after which the leash stops working.
    /// @param allowedPayees Registry names the agent may pay. Empty = any confirmed payee.
    function createLeash(
        address agent,
        uint128 budget,
        uint64 period,
        uint128 perPaymentCap,
        uint64 expiry,
        string[] calldata allowedPayees
    ) external returns (uint256 leashId) {
        if (agent == address(0)) revert ZeroAddress();
        if (budget == 0 || perPaymentCap == 0 || expiry <= block.timestamp) revert InvalidLeash();
        leashId = ++leashCount;
        LeashData storage l = _leashes[leashId];
        l.owner = msg.sender;
        l.agent = agent;
        l.expiry = expiry;
        l.period = period;
        l.periodStart = uint64(block.timestamp);
        l.budget = budget;
        l.perPaymentCap = perPaymentCap;
        l.allowlistOnly = allowedPayees.length > 0;
        _leashesOf[msg.sender].push(leashId);
        emit LeashCreated(leashId, msg.sender, agent, budget, period, perPaymentCap, expiry, l.allowlistOnly);
        for (uint256 i = 0; i < allowedPayees.length; i++) {
            _setPayeeAllowed(leashId, allowedPayees[i], true);
        }
    }

    /// @notice Add or remove a payee on an allowlist-only leash.
    function setPayeeAllowed(uint256 leashId, string calldata name, bool allowed) external {
        if (_leashes[leashId].owner != msg.sender) revert NotOwner();
        _leashes[leashId].allowlistOnly = true;
        _setPayeeAllowed(leashId, name, allowed);
    }

    function _setPayeeAllowed(uint256 leashId, string calldata name, bool allowed) internal {
        bytes32 h = keccak256(bytes(name));
        if (allowed && !_everListed[leashId][h]) {
            _everListed[leashId][h] = true;
            _allowlistNames[leashId].push(name);
        }
        payeeAllowed[leashId][h] = allowed;
        emit PayeeAllowlisted(leashId, h, name, allowed);
    }

    /// @notice Cut the leash. Takes effect in the same block; signed intents die with it.
    function revoke(uint256 leashId) external {
        LeashData storage l = _leashes[leashId];
        if (l.owner != msg.sender) revert NotOwner();
        l.revoked = true;
        emit LeashRevoked(leashId);
    }

    // ───────────────────────────── Merchant: invoices ───────────────────────

    /// @notice Bill `payer`. The caller must hold a name in the PayeeRegistry.
    function createInvoice(address payer, uint128 amount, uint64 dueBy, string calldata memo)
        external
        returns (uint256 invoiceId)
    {
        if (payer == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        bytes32 nameHash = registry.nameHashOf(msg.sender);
        if (nameHash == bytes32(0)) revert PayeeNotRegistered();
        invoiceId = ++invoiceCount;
        Invoice storage inv = _invoices[invoiceId];
        inv.payee = msg.sender;
        inv.payer = payer;
        inv.amount = amount;
        inv.dueBy = dueBy;
        inv.status = InvoiceStatus.Open;
        inv.payeeNameHash = nameHash;
        inv.memo = memo;
        _invoicesFor[payer].push(invoiceId);
        _invoicesBy[msg.sender].push(invoiceId);
        emit InvoiceCreated(invoiceId, msg.sender, payer, amount, dueBy, nameHash, memo);
    }

    function cancelInvoice(uint256 invoiceId) external {
        Invoice storage inv = _invoices[invoiceId];
        if (inv.payee != msg.sender) revert NotPayee();
        if (inv.status != InvoiceStatus.Open) revert Refused(Check.InvoiceNotOpen);
        inv.status = InvoiceStatus.Cancelled;
        emit InvoiceCancelled(invoiceId);
    }

    // ───────────────────────────── Paying ───────────────────────────────────

    /// @notice Settle an invoice with an intent signed by the leash's agent key.
    ///         Anyone may submit it; the merchant usually does, and pays the gas.
    ///         An invoice can be paid once, so resubmitting is harmless.
    function payWithIntent(PaymentIntent calldata intent, bytes calldata signature) external nonReentrant {
        Check c = _check(intent, signature);
        if (c != Check.Ok) revert Refused(c);

        LeashData storage l = _leashes[intent.leashId];
        Invoice storage inv = _invoices[intent.invoiceId];
        uint128 amount = inv.amount;

        if (l.period != 0 && block.timestamp >= uint256(l.periodStart) + l.period) {
            uint256 elapsed = (block.timestamp - l.periodStart) / l.period;
            l.periodStart += uint64(elapsed * l.period);
            l.spentInPeriod = 0;
        }
        l.spentInPeriod += amount;
        l.totalSpent += amount;
        vaultOf[l.owner] -= amount;
        _settle(inv, intent.invoiceId, intent.leashId, amount);
    }

    /// @notice The owner pays an invoice from the vault directly. This is the
    ///         human approval path for anything the agent's leash refuses.
    function payAsOwner(uint256 invoiceId) external nonReentrant {
        Invoice storage inv = _invoices[invoiceId];
        if (inv.status != InvoiceStatus.Open) revert Refused(Check.InvoiceNotOpen);
        if (inv.payer != msg.sender) revert Refused(Check.WrongPayer);
        if (registry.accountOf(inv.payeeNameHash) != inv.payee) revert Refused(Check.PayeeMismatch);
        uint128 amount = inv.amount;
        if (vaultOf[msg.sender] < amount) revert Refused(Check.InsufficientVault);
        vaultOf[msg.sender] -= amount;
        _settle(inv, invoiceId, 0, amount);
    }

    function _settle(Invoice storage inv, uint256 invoiceId, uint256 leashId, uint128 amount) internal {
        inv.status = InvoiceStatus.Paid;
        inv.paidAt = uint64(block.timestamp);
        inv.paidByLeash = leashId;
        token.safeTransfer(inv.payee, amount);
        emit InvoicePaid(invoiceId, leashId, inv.payee, inv.payer, amount, msg.sender);
    }

    // ───────────────────────────── Views ────────────────────────────────────

    /// @notice Dry-run a payment. Agents and UIs call this to explain a refusal
    ///         before anyone spends gas.
    function preview(PaymentIntent calldata intent, bytes calldata signature) external view returns (Check) {
        return _check(intent, signature);
    }

    /// @notice Same as `preview` but skips the signature, for an agent deciding
    ///         whether an invoice is worth signing.
    function previewUnsigned(PaymentIntent calldata intent) external view returns (Check) {
        return _checkRules(intent);
    }

    function _check(PaymentIntent calldata intent, bytes calldata signature) internal view returns (Check) {
        LeashData storage l = _leashes[intent.leashId];
        if (l.owner == address(0)) return Check.LeashNotFound;
        (address signer, ECDSA.RecoverError err,) = ECDSA.tryRecover(hashIntent(intent), signature);
        if (err != ECDSA.RecoverError.NoError || signer != l.agent) return Check.BadSignature;
        return _checkRules(intent);
    }

    function _checkRules(PaymentIntent calldata intent) internal view returns (Check) {
        LeashData storage l = _leashes[intent.leashId];
        if (l.owner == address(0)) return Check.LeashNotFound;
        if (l.revoked) return Check.LeashRevoked;
        if (block.timestamp >= l.expiry) return Check.LeashExpired;
        if (block.timestamp > intent.deadline) return Check.IntentExpired;

        Invoice storage inv = _invoices[intent.invoiceId];
        if (inv.status != InvoiceStatus.Open) return Check.InvoiceNotOpen;
        if (inv.dueBy != 0 && block.timestamp > inv.dueBy) return Check.InvoiceOverdue;
        if (inv.payer != l.owner) return Check.WrongPayer;
        if (intent.amount != inv.amount) return Check.AmountMismatch;
        // Confirmation of Payee: the name the agent believes it is paying must
        // still be registered to the address that will receive the money.
        if (
            intent.payee != inv.payee || intent.payeeNameHash != inv.payeeNameHash
                || registry.accountOf(intent.payeeNameHash) != inv.payee
        ) return Check.PayeeMismatch;
        if (l.allowlistOnly && !payeeAllowed[intent.leashId][intent.payeeNameHash]) return Check.PayeeNotAllowed;
        if (inv.amount > l.perPaymentCap) return Check.OverPaymentCap;
        if (uint256(_spentNow(l)) + inv.amount > l.budget) return Check.OverBudget;
        if (vaultOf[l.owner] < inv.amount) return Check.InsufficientVault;
        return Check.Ok;
    }

    function _spentNow(LeashData storage l) internal view returns (uint128) {
        if (l.period != 0 && block.timestamp >= uint256(l.periodStart) + l.period) return 0;
        return l.spentInPeriod;
    }

    function hashIntent(PaymentIntent calldata intent) public view returns (bytes32) {
        return _hashTypedDataV4(
            keccak256(
                abi.encode(
                    INTENT_TYPEHASH,
                    intent.leashId,
                    intent.invoiceId,
                    intent.payee,
                    intent.payeeNameHash,
                    intent.amount,
                    intent.deadline
                )
            )
        );
    }

    function getLeash(uint256 leashId) external view returns (LeashData memory) {
        return _leashes[leashId];
    }

    /// @notice Budget left in the current period.
    function remainingBudget(uint256 leashId) external view returns (uint256) {
        LeashData storage l = _leashes[leashId];
        uint128 spent = _spentNow(l);
        return spent >= l.budget ? 0 : l.budget - spent;
    }

    /// @notice Names currently on a leash's allowlist.
    function allowlistOf(uint256 leashId) external view returns (string[] memory names) {
        string[] storage all = _allowlistNames[leashId];
        uint256 n;
        for (uint256 i = 0; i < all.length; i++) {
            if (payeeAllowed[leashId][keccak256(bytes(all[i]))]) n++;
        }
        names = new string[](n);
        uint256 j;
        for (uint256 i = 0; i < all.length; i++) {
            if (payeeAllowed[leashId][keccak256(bytes(all[i]))]) names[j++] = all[i];
        }
    }

    function getInvoice(uint256 invoiceId) external view returns (Invoice memory) {
        return _invoices[invoiceId];
    }

    function leashesOf(address owner) external view returns (uint256[] memory) {
        return _leashesOf[owner];
    }

    function invoicesFor(address payer) external view returns (uint256[] memory) {
        return _invoicesFor[payer];
    }

    function invoicesBy(address payee) external view returns (uint256[] memory) {
        return _invoicesBy[payee];
    }
}
