"""
Homework 3 (hw3-2): figures as a multi-page PDF.

Page 1 — Problems 1(a), 1(b), 1(c), 2
Page 2 — Problems 3(a), 3(b), 4
Page 3 — Problems 5(a)–(d)
"""

from __future__ import annotations

import argparse
import math
from typing import Any

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages


def _annotate_page(fig: Any, title: str, *, use_tight_layout: bool = True) -> None:
    fig.suptitle(title, fontsize=12, y=0.98)
    if use_tight_layout:
        fig.tight_layout(rect=[0, 0, 1, 0.96])


def homework_problem_1a(ax: Any, a_grid: np.ndarray) -> None:
    """
    Problem 1(a). States rho_0 = |+><+|, rho_1 = |psi><psi| with
    |psi> = sqrt(a)|0> + sqrt(1-a)|1>. For each pi_0 in {0.1,...,0.5},
    plot optimal P_c versus a in [0,1].
    """
    # Helstrom (equal dimension, mixed states): P_c = (1 + ||pi_0 rho_0 - pi_1 rho_1||_1)/2.
    # For pure |p>, |q>: ||pi_0|p><p| - pi_1|q><q|||_1 = sqrt(1 - 4 pi_0 pi_1 |<p|q>|^2)
    # (when the right-hand side is nonnegative), hence
    # P_c = (1/2)(1 + sqrt(1 - 4 pi_0 pi_1 s)), with s = |<+|psi>|^2.

    for pi0 in [0.1, 0.2, 0.3, 0.4, 0.5]:
        # Prior on H1: pi_1 = 1 - pi_0 (binary hypothesis).
        pi1 = 1.0 - pi0

        pcs: list[float] = []
        for a in a_grid:
            # Bloch overlap: |+> = (|0>+|1>)/sqrt(2); <+|psi(a)> = (sqrt(a)+sqrt(1-a))/sqrt(2).
            # s = |<+|psi>|^2 = ((sqrt(a)+sqrt(1-a))^2)/2 = 1/2 + sqrt(a(1-a)).
            s = 0.5 * (1.0 + 2.0 * math.sqrt(max(float(a) * (1.0 - float(a)), 0.0)))

            # Discriminant inside the Helstrom formula: Delta = 1 - 4 pi_0 pi_1 s.
            disc = 1.0 - 4.0 * pi0 * pi1 * s
            # Optimal correct-detection probability: P_c = (1/2)(1 + sqrt(Delta)).
            pc = 0.5 * (1.0 + math.sqrt(max(disc, 0.0)))
            pcs.append(pc)

        ax.plot(a_grid, pcs, label=rf"$\pi_0={pi0:.1f}$")

    ax.set_xlabel(r"$a$")
    ax.set_ylabel(r"$P_c$")
    ax.set_title(r"Problem 1(a): $P_c$ vs $a$ (Helstrom, pure qubits)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0.5, 1.0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def homework_problem_1b(ax: Any) -> None:
    """
    Problem 1(b). Fix a in {0.1,...,0.5}. Quantum ROC: P_d vs P_f from rank-1
    projectors P(theta) = |e(theta)><e(theta)| with |e> = cos(theta)|0>+sin(theta)|1>.
    """
    # ROC generated using the Helstrom projectors (same structure as Problem 1(a)).
    # For each prior ratio (pi0, pi1=1-pi0), build the discriminant
    #   D = pi0*rho0 - pi1*rho1
    # and choose the POVM element Pi1 as the projector onto the negative eigenspace of D.
    #
    # Then the ROC coordinates are
    #   P_f = Tr(Pi1 rho0)  (false alarm: decide H1 while H0 is true)
    #   P_d = Tr(Pi1 rho1)  (detection: decide H1 while H1 is true)

    # State for H0: |+> = (|0>+|1>)/sqrt(2).
    plus = np.array([1.0, 1.0], dtype=float) / math.sqrt(2.0)
    rho0 = np.outer(plus, plus)

    # Prior sweep to generate a smooth ROC curve.
    # (Varying pi0 continuously varies the Helstrom threshold, hence changes Pi1.)
    pi0_grid = np.linspace(0.01, 0.99, 300)
    tol = 1e-12

    for a in [0.1, 0.2, 0.3, 0.4, 0.5]:
        # State for H1: |psi(a)> = sqrt(a)|0> + sqrt(1-a)|1>.
        psi = np.array([math.sqrt(a), math.sqrt(1.0 - a)], dtype=float)
        rho1 = np.outer(psi, psi)

        pfs: list[float] = []
        pds: list[float] = []
        for pi0 in pi0_grid:
            pi1 = 1.0 - pi0

            # Discriminant D = pi0*rho0 - pi1*rho1.
            D = pi0 * rho0 - pi1 * rho1

            # Projector onto the negative eigenspace: Pi1 = sum_{neg} |v><v|.
            evals, evecs = np.linalg.eigh(D)
            Pi1 = np.zeros((2, 2), dtype=float)
            for i, ev in enumerate(evals):
                if ev < -tol:
                    v = evecs[:, i]
                    Pi1 += np.outer(v, v)

            # ROC coordinates:
            # P_f = Tr(Pi1 rho0), P_d = Tr(Pi1 rho1).
            pf = float(np.real(np.trace(Pi1 @ rho0)))
            pd = float(np.real(np.trace(Pi1 @ rho1)))
            pfs.append(pf)
            pds.append(pd)

        # Sort by P_f for a proper ROC rendering.
        pfs_arr = np.asarray(pfs)
        pds_arr = np.asarray(pds)
        idx = np.argsort(pfs_arr)
        pfs_arr = pfs_arr[idx]
        pds_arr = pds_arr[idx]

        ax.plot(pfs_arr, pds_arr, label=f"a={a:.1f}", linewidth=0.7, alpha=0.8)

    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="random guess")
    ax.set_xlabel(r"$P_f$")
    ax.set_ylabel(r"$P_d$")
    ax.set_title(r"Problem 1(b): quantum ROC ($P_d$ vs $P_f$)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)


def homework_problem_1c(ax: Any, a_grid: np.ndarray) -> None:
    """
    Problem 1(c). Quantum Chernoff "distance" / divergence rate for two pure states:
    C = -log |<+|psi(a)>|^2 (single-copy quantum Chernoff quantity for pure vs pure).
    """
    cvals: list[float] = []
    for a in a_grid:
        # s(a) = |<+|psi(a)>|^2 = 1/2 + sqrt(a(1-a)).
        s = 0.5 * (1.0 + 2.0 * math.sqrt(max(float(a) * (1.0 - float(a)), 0.0)))
        # Quantum Chernoff quantity (pure states): xi_QCB = -log s; plot C = xi_QCB vs a.
        cvals.append(-math.log(max(s, 1e-15)))

    ax.plot(a_grid, cvals, linewidth=2)
    ax.set_xlabel(r"$a$")
    ax.set_ylabel(r"$C(\rho_0,\rho_1)$")
    ax.set_title(r"Problem 1(c): quantum Chernoff quantity vs $a$")
    ax.set_xlim(0, 1)
    ax.grid(alpha=0.3)


def homework_problem_2(ax: Any, p_grid: np.ndarray) -> None:
    """
    Problem 2. Equal prior on channels;
    N(rho) = (1-p) rho + p Z rho Z (dephasing), M(rho) = (1-p) rho + (p/2) I (depolarizing).
    (a) Probe rho = |+><+|. (b) Probe |Phi+><Phi+| on two qubits (same figure).
    Helstrom: P_c = (1/2)(1 + (1/2)||rho_out^N - rho_out^M||_1).
    """
    # Probe for (a): |+> = (|0>+|1>)/sqrt(2).
    plus = np.array([1.0, 1.0], dtype=float) / math.sqrt(2.0)
    # Orthogonal companion: |-> = (|0>-|1>)/sqrt(2); dephasing: |+> -> |-> with prob p.
    minus = np.array([1.0, -1.0], dtype=float) / math.sqrt(2.0)
    # Density matrix rho_plus = |+><+|.
    rho_plus = np.outer(plus, plus)
    # rho_minus = |-><-|.
    rho_minus = np.outer(minus, minus)
    # Single-qubit identity I_2.
    i2 = np.eye(2)

    # Two-qubit Bell probe for 2(b): |Phi+> = (1/sqrt(2))(|00>+|11>).
    phi_plus = np.array([1.0, 0.0, 0.0, 1.0], dtype=float) / math.sqrt(2.0)
    # |Phi-> = (1/sqrt(2))(|00>-|11>) (useful identity: (Z \otimes I)|Phi+> = |Phi->).
    phi_minus = np.array([1.0, 0.0, 0.0, -1.0], dtype=float) / math.sqrt(2.0)
    rho_phi_plus = np.outer(phi_plus, phi_plus)
    # Single-qubit Pauli-Z and embedded action on probe qubit only: Z \otimes I.
    z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=float)
    z_on_probe = np.kron(z, i2)

    def helstrom_pc_equal_prior(rho_a: np.ndarray, rho_b: np.ndarray) -> float:
        # Difference Delta = rho_a - rho_b.
        delta = rho_a - rho_b
        # Trace (Schatten-1) norm: ||Delta||_1 = sum_k sigma_k(Delta).
        svals = np.linalg.svd(delta, compute_uv=False)
        tr_norm = float(np.sum(np.abs(svals)))
        # Equal priors: P_c = 1/2 + (1/4)||Delta||_1.
        return 0.5 + 0.25 * tr_norm

    def partial_trace_probe(rho_ab: np.ndarray) -> np.ndarray:
        # Partial trace over probe qubit A (basis ordering |a,b>):
        # [rho_B]_{b,b'} = sum_{a=0}^1 <a,b| rho_AB |a,b'>.
        rho_b = np.zeros((2, 2), dtype=float)
        for b in range(2):
            for bp in range(2):
                rho_b[b, bp] = rho_ab[0 * 2 + b, 0 * 2 + bp] + rho_ab[1 * 2 + b, 1 * 2 + bp]
        return rho_b

    pc_un: list[float] = []
    pc_en: list[float] = []
    for p in p_grid:
        # Unentangled output under N: (1-p)|+><+| + p |-><-|.
        rho_n = (1.0 - p) * rho_plus + p * rho_minus
        # Under M: (1-p)|+><+| + (p/2) I.
        rho_m = (1.0 - p) * rho_plus + 0.5 * p * i2
        pc_un.append(helstrom_pc_equal_prior(rho_n, rho_m))

        # Entangled 2(b): apply channel to ONE qubit only (probe), ancilla untouched.
        # (N \otimes I)(rho_AB) = (1-p)rho_AB + p (Z \otimes I) rho_AB (Z \otimes I).
        rho_n2 = (1.0 - p) * rho_phi_plus + p * (z_on_probe @ rho_phi_plus @ z_on_probe)
        # (M \otimes I)(rho_AB) = (1-p)rho_AB + p (I/2 \otimes Tr_A[rho_AB]).
        rho_b = partial_trace_probe(rho_phi_plus)
        rho_m2 = (1.0 - p) * rho_phi_plus + p * np.kron(0.5 * i2, rho_b)
        pc_en.append(helstrom_pc_equal_prior(rho_n2, rho_m2))

    ax.plot(p_grid, np.asarray(pc_un), linewidth=2, label=r"unentangled $|+\rangle\langle+|$")
    ax.plot(p_grid, np.asarray(pc_en), linewidth=2, label=r"entangled $|\Phi^+\rangle\langle\Phi^+|$")
    ax.set_xlabel(r"$p$")
    ax.set_ylabel(r"$P_c$")
    ax.set_title(r"Problem 2: channel discrimination, $P_c$ vs $p$")
    ax.set_xlim(0, 1)
    ax.set_ylim(0.5, 1.0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def homework_problem_3a(ax: Any, eta: float, lam: float, d: float, n: int) -> None:
    """
    Problem 3(a). LOCC ROC under Gaussian approximation, N = 100.
    Course template: effective SNR per copy = eta * lam * (1 or d); means 0 vs sqrt(n * SNR).
    """
    for entangled, label in [
        (False, f"LOCC unentangled (N={n})"),
        (True, f"LOCC entangled (N={n})"),
    ]:
        # SNR_copy = eta * lambda * (d if entangled else 1).
        snr = eta * lam * (d if entangled else 1.0)
        # H0 mean mu_0 = 0; H1 mean mu_1 = sqrt(n * SNR_copy) (Gaussian sufficient statistic).
        mu0 = 0.0
        mu1 = math.sqrt(n * snr)
        taus = np.linspace(-6.0, mu1 + 6.0, 1200)
        erf_vec = np.vectorize(lambda t: math.erf(float(t) / math.sqrt(2.0)))
        # Tail model used in reference: P_f(tau) = 1/2 - (1/2) erf((tau - mu_0)/sqrt(2)).
        pf = 0.5 - 0.5 * erf_vec(taus - mu0)
        # P_d(tau) = 1/2 - (1/2) erf((tau - mu_1)/sqrt(2)).
        pd = 0.5 - 0.5 * erf_vec(taus - mu1)
        ax.plot(pf, pd, linewidth=2, label=label)

    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="random guess")
    ax.set_xlabel(r"$P_f$")
    ax.set_ylabel(r"$P_d$")
    ax.set_title(r"Problem 3(a): LOCC ROC (Gaussian approximation, $N=100$)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)


def homework_problem_3b(ax: Any, eta: float, lam: float, d: float) -> None:
    """
    Problem 3(b). Chernoff-type bounds P_e <= (1/2) exp(-n C) with
    C_q = SNR/4 (quantum/protocol) and C_c = SNR/8 (classical LOCC), SNR = eta*lambda or eta*lambda*d.
    """
    n_vals = np.arange(1, 301, dtype=float)
    # Unentangled effective SNR: SNR_un = eta * lambda.
    snr_un = eta * lam
    # Entangled: SNR_en = eta * lambda * d.
    snr_en = eta * lam * d
    # Quantum Chernoff-rate placeholder in template: C_q = SNR / 4.
    c_q_un = snr_un / 4.0
    c_q_en = snr_en / 4.0
    # Classical LOCC counterpart in template: C_c = SNR / 8.
    c_c_un = snr_un / 8.0
    c_c_en = snr_en / 8.0
    # Upper bound curve: P_e^{UB}(n) = (1/2) exp(-n C).
    ax.semilogy(n_vals, 0.5 * np.exp(-n_vals * c_q_un), linewidth=2, label="quantum Chernoff (unentangled)")
    ax.semilogy(n_vals, 0.5 * np.exp(-n_vals * c_q_en), linewidth=2, label="quantum Chernoff (entangled)")
    ax.semilogy(n_vals, 0.5 * np.exp(-n_vals * c_c_un), "--", linewidth=2, label="classical LOCC Chernoff (unentangled)")
    ax.semilogy(n_vals, 0.5 * np.exp(-n_vals * c_c_en), "--", linewidth=2, label="classical LOCC Chernoff (entangled)")
    ax.set_xlabel(r"$N$")
    ax.set_ylabel(r"$P_e$ upper bound")
    ax.set_title("Problem 3(b): Chernoff-bound exponentials vs $N$")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=7)


def homework_problem_4(ax: Any) -> None:
    """
    Problem 4. N copies, equal prior: local single-copy Helstrom on each qubit + optimal
    lumped threshold (simulated) vs globally optimal LOCC unanimity: P_c = 1 - (1/2) s^N,
    s = |<+|psi(a)>|^2.
    """
    a_values = np.arange(0.1, 1.0, 0.1)
    rng = np.random.default_rng(42)
    n_trials = 20000
    plus = np.array([1.0, 1.0], dtype=float) / math.sqrt(2.0)
    rho0 = np.outer(plus, plus)

    for n in [5, 10]:
        pcs_local: list[float] = []
        pcs_unanimity: list[float] = []
        for a in a_values:
            psi = np.array([math.sqrt(a), math.sqrt(1.0 - a)], dtype=float)
            rho1 = np.outer(psi, psi)

            # Helstrom operator for single copy: Pi_1 projects onto negative eigenspace of (rho0 - rho1).
            delta = rho0 - rho1
            evals, evecs = np.linalg.eigh(delta)
            pi1 = np.zeros((2, 2), dtype=float)
            for i, ev in enumerate(evals):
                if ev < -1e-12:
                    v = evecs[:, i]
                    pi1 += np.outer(v, v)
            # Error probs under each hypothesis for deciding "1": q_j = Tr(Pi_1 rho_j).
            q0 = float(np.trace(pi1 @ rho0))
            q1 = float(np.trace(pi1 @ rho1))
            q0 = float(np.clip(q0, 1e-12, 1.0 - 1e-12))
            q1 = float(np.clip(q1, 1e-12, 1.0 - 1e-12))

            # Optimal threshold on count K of "click" outcomes: LLR(K) = K log(q1/q0) + (N-K) log((1-q1)/(1-q0)).
            tau = n + 1
            for k in range(n + 1):
                llr = k * math.log(q1 / q0) + (n - k) * math.log((1.0 - q1) / (1.0 - q0))
                if llr >= 0.0:
                    tau = k
                    break

            h = rng.integers(0, 2, size=n_trials)
            probs = np.where(h == 0, q0, q1)
            ksamples = rng.binomial(n, probs)
            dec = (ksamples >= tau).astype(int)
            pcs_local.append(float(np.mean(dec == h)))

            # Overlap: s = |<+|psi>|^2 = 1/2 + sqrt(a(1-a)).
            s = 0.5 * (1.0 + 2.0 * math.sqrt(max(float(a) * (1.0 - float(a)), 0.0)))
            # Unanimity success probability: P_c = 1 - (1/2) s^N.
            pcs_unanimity.append(1.0 - 0.5 * (s**n))

        ax.plot(a_values, pcs_local, "o-", linewidth=2, label=f"local optimal sim (N={n})")
        ax.plot(a_values, pcs_unanimity, "s--", linewidth=2, label=f"unanimity closed-form (N={n})")

    ax.set_xlabel(r"$a$")
    ax.set_ylabel(r"$P_c$")
    ax.set_title(r"Problem 4: multi-copy $P_c$ vs $a$ ($N=5,10$)")
    ax.set_xlim(0.1, 0.9)
    ax.set_ylim(0.5, 1.0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def homework_problem_5a(ax: Any) -> None:
    """
    Problem 5(a). |psi> = |Phi+>, |phi> = |+>|->. SWAP-test estimator for F = |<psi|phi>|^2:
    each trial yields Bernoulli(p) with p = (1+F)/2; estimate hat F = max(0, 2 hat p - 1).
    """
    phi_plus = np.array([1.0, 0.0, 0.0, 1.0], dtype=float) / math.sqrt(2.0)
    plus = np.array([1.0, 1.0], dtype=float) / math.sqrt(2.0)
    minus = np.array([1.0, -1.0], dtype=float) / math.sqrt(2.0)
    # Product state |phi> = |+> \otimes |-> (order A then B).
    phi = np.kron(plus, minus)
    # True squared overlap: F = |<Phi+|phi>|^2.
    true_overlap = float(abs(np.vdot(phi_plus, phi)) ** 2)
    # Expected "accept" probability for the SWAP observable setup: p = (1 + F)/2.
    p_accept = 0.5 * (1.0 + true_overlap)
    rng = np.random.default_rng(7)
    n_values = np.arange(10, 201, 10)
    est: list[float] = []
    for n in n_values:
        # i.i.d. Bernoulli trials X_i ~ Bern(p_accept); hat p = (1/n) sum_i X_i.
        acc = rng.binomial(1, p_accept, size=int(n))
        hat_p = float(np.mean(acc))
        # Method-of-moments inversion: hat F = clip(2 hat p - 1, 0, 1).
        est.append(float(np.clip(2.0 * hat_p - 1.0, 0.0, 1.0)))

    ax.plot(n_values, [true_overlap] * len(n_values), "k--", linewidth=2, label="true overlap")
    ax.plot(n_values, est, "o-", linewidth=2, label="SWAP-test estimate")
    ax.set_xlabel("number of state-pair copies N")
    ax.set_ylabel(r"$|\langle \psi | \phi \rangle|^2$")
    ax.set_title(r"Problem 5(a): SWAP observable, estimate vs $N$")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def homework_problem_5b(ax: Any, a_values: np.ndarray, ns: list[int]) -> None:
    """
    Problem 5(b). Equality test on Problem-1 pure states: single-shot acceptance
    p_eq(a) = (1 + |<+|psi(a)>|^2)/2; N-copy AND gives P(declare equal) = p_eq^N.
    """
    for n in ns:
        vals: list[float] = []
        for a in a_values:
            # s(a) = |<+|psi(a)>|^2 = 1/2 + sqrt(a(1-a)).
            s = 0.5 * (1.0 + 2.0 * math.sqrt(max(float(a) * (1.0 - float(a)), 0.0)))
            # Equality-test acceptance probability: p_eq = (1 + s)/2.
            p_eq = 0.5 * (1.0 + s)
            # Independent trials: P(all declare equality) = p_eq^N (template in course homework).
            vals.append(p_eq**n)
        ax.plot(a_values, vals, "o-", linewidth=2, label=f"N={n}")

    ax.set_xlabel(r"$a$")
    ax.set_ylabel(r"$P_e$ (declare equality)")
    ax.set_title(r"Problem 5(b): equality test")
    ax.set_xlim(0.1, 0.9)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def homework_problem_5c(ax: Any, a_values: np.ndarray, ns: list[int]) -> None:
    """
    Problem 5(c). Mixed state rho = a |+><+| + (1-a)|-><-|. Purity-test acceptance model
    p_pure(a) = (1 + Tr(rho^2))/2 = (1 + a^2 + (1-a)^2)/2; plot P_e = p_pure^N.
    """
    for n in ns:
        vals: list[float] = []
        for a in a_values:
            # For this mixture, Tr(rho^2) = a^2 + (1-a)^2.
            tr_rho_sq = float(a) ** 2 + (1.0 - float(a)) ** 2
            # Acceptance probability: p_pure = (1 + Tr(rho^2))/2.
            p_pure = 0.5 * (1.0 + tr_rho_sq)
            vals.append(p_pure**n)
        ax.plot(a_values, vals, "o-", linewidth=2, label=f"N={n}")

    ax.set_xlabel(r"$a$")
    ax.set_ylabel(r"$P_e$ (declare pure)")
    ax.set_title(r"Problem 5(c): purity test")
    ax.set_xlim(0.1, 0.9)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def homework_problem_5d(ax: Any, a_values: np.ndarray, ns: list[int]) -> None:
    r"""
    Problem 5(d). State on AB after CNOT with B as control:
    $|\psi\rangle_{AB} = \mathrm{CX}\,|0\rangle_A \otimes (\sqrt{a}\,|0\rangle_B + \sqrt{1-a}\,|1\rangle_B)$.
    Product-test acceptance uses the same closed-form $p_{\mathrm{prod}}(a) = (1 + a^2 + (1-a)^2)/2$ as in the HW template.
    """
    for n in ns:
        vals: list[float] = []
        for a in a_values:
            # Template closed form (matches reduced-state purity overlap for this family): p_prod = (1 + a^2 + (1-a)^2)/2.
            p_prod = 0.5 * (1.0 + float(a) ** 2 + (1.0 - float(a)) ** 2)
            vals.append(p_prod**n)
        ax.plot(a_values, vals, "o-", linewidth=2, label=f"N={n}")

    ax.set_xlabel(r"$a$")
    ax.set_ylabel(r"$P_e$ (declare separable)")
    ax.set_title(r"Problem 5(d): product test")
    ax.set_xlim(0.1, 0.9)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def write_homework_pdf(path: str) -> None:
    a_grid = np.linspace(0.0, 1.0, 501)
    p_grid = np.linspace(0.0, 1.0, 501)
    # Problem 3 parameters from the assignment PDF.
    eta, lam, d = 0.4, 0.1, 4.0
    n_qi = 100
    a_values = np.arange(0.1, 1.0, 0.1)
    ns = [5, 10]

    with PdfPages(path) as pdf:
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        homework_problem_1a(axes[0, 0], a_grid)
        homework_problem_1b(axes[0, 1])
        homework_problem_1c(axes[1, 0], a_grid)
        homework_problem_2(axes[1, 1], p_grid)
        _annotate_page(fig, "Problems 1(a–c) and 2")
        pdf.savefig(fig)
        plt.close(fig)

        # Use a standard 2x2 grid so panel sizes match other pages.
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        homework_problem_3a(axes[0, 0], eta, lam, d, n_qi)
        homework_problem_3b(axes[0, 1], eta, lam, d)
        homework_problem_4(axes[1, 0])
        axes[1, 1].set_visible(False)
        _annotate_page(fig, "Problems 3(a, b) and 4")
        pdf.savefig(fig)
        plt.close(fig)

        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        homework_problem_5a(axes[0, 0])
        homework_problem_5b(axes[0, 1], a_values, ns)
        homework_problem_5c(axes[1, 0], a_values, ns)
        homework_problem_5d(axes[1, 1], a_values, ns)
        _annotate_page(fig, "Problem 5 (a–d)")
        pdf.savefig(fig)
        plt.close(fig)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Write HW3 (hw3-2) figures to a single PDF.")
    p.add_argument(
        "-o",
        "--output",
        type=str,
        default="cursor3_homework.pdf",
        help="Output PDF path (default: cursor3_homework.pdf)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    write_homework_pdf(args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
