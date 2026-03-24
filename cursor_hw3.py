import argparse
import os

import numpy as np
import matplotlib.pyplot as plt


def ket_plus() -> np.ndarray:
    return np.array([1.0, 1.0], dtype=float) / np.sqrt(2.0)


def ket_psi(a: float) -> np.ndarray:
    return np.array([np.sqrt(a), np.sqrt(1.0 - a)], dtype=float)


def density_from_ket(ket: np.ndarray) -> np.ndarray:
    return np.outer(ket, ket)


def overlap_squared(a: float) -> float:
    """|<+|psi(a)>|^2."""
    amp = np.vdot(ket_plus(), ket_psi(a))
    return float(np.abs(amp) ** 2)


def helstrom_pc(a: float, pi0: float) -> float:
    """Optimal single-copy success probability for priors pi0 and pi1."""
    pi1 = 1.0 - pi0
    s = overlap_squared(a)
    inside = max(0.0, 1.0 - 4.0 * pi0 * pi1 * s)
    return 0.5 * (1.0 + np.sqrt(inside))


def projective_roc_points(a: float, n_theta: int = 4000) -> tuple[np.ndarray, np.ndarray]:
    """
    Approximate optimal quantum ROC by scanning real projective measurements.

    The states are real in the computational basis, so a real-angle scan is enough.
    """
    plus = ket_plus()
    psi = ket_psi(a)

    thetas = np.linspace(0.0, np.pi, n_theta, endpoint=False)
    pfs = np.zeros_like(thetas)
    pds = np.zeros_like(thetas)

    for i, theta in enumerate(thetas):
        e1 = np.array([np.cos(theta), np.sin(theta)], dtype=float)
        pfs[i] = np.abs(np.vdot(e1, plus)) ** 2
        pds[i] = np.abs(np.vdot(e1, psi)) ** 2

    # Upper envelope over Pf to approximate Neyman-Pearson optimal frontier.
    idx = np.argsort(pfs)
    pfs_sorted = pfs[idx]
    pds_sorted = pds[idx]

    unique_pf = []
    best_pd = []
    i = 0
    while i < len(pfs_sorted):
        j = i + 1
        while j < len(pfs_sorted) and np.isclose(pfs_sorted[j], pfs_sorted[i], atol=1e-6):
            j += 1
        unique_pf.append(float(np.mean(pfs_sorted[i:j])))
        best_pd.append(float(np.max(pds_sorted[i:j])))
        i = j

    return np.array(unique_pf), np.array(best_pd)


def quantum_chernoff_distance(a: float) -> float:
    """
    Quantum Chernoff distance C = -log(min_s Tr[rho0^s rho1^(1-s)]).
    For pure states, this is -log(|<psi0|psi1>|^2).
    """
    s = max(overlap_squared(a), 1e-15)
    return float(-np.log(s))


def plot_pc_vs_a(a_grid: np.ndarray) -> None:
    priors = [0.1, 0.2, 0.3, 0.4, 0.5]
    plt.figure(figsize=(8, 5))
    for pi0 in priors:
        pcs = [helstrom_pc(a, pi0) for a in a_grid]
        plt.plot(a_grid, pcs, label=rf"$\pi_0={pi0:.1f}$")
    plt.xlabel("a")
    plt.ylabel(r"$P_c$")
    plt.title(r"Problem 1(a): Optimal $P_c$ vs $a$")
    plt.xlim(0, 1)
    plt.ylim(0.5, 1.0)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("hw3_p1a_pc_vs_a.png", dpi=200)


def plot_roc_curves() -> None:
    a_values = [0.1, 0.2, 0.3, 0.4, 0.5]
    plt.figure(figsize=(8, 6))
    for a in a_values:
        pf, pd = projective_roc_points(a)
        plt.plot(pf, pd, label=rf"$a={a:.1f}$")
    plt.plot([0, 1], [0, 1], "k--", alpha=0.5, label="random guess")
    plt.xlabel(r"$P_f$")
    plt.ylabel(r"$P_d$")
    plt.title(r"Problem 1(b): Quantum ROC Curves")
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("hw3_p1b_roc.png", dpi=200)


def plot_chernoff_vs_a(a_grid: np.ndarray) -> None:
    cvals = [quantum_chernoff_distance(a) for a in a_grid]
    plt.figure(figsize=(8, 5))
    plt.plot(a_grid, cvals, linewidth=2)
    plt.xlabel("a")
    plt.ylabel(r"$C(\rho_0,\rho_1)$")
    plt.title(r"Problem 1(c): Quantum Chernoff Distance vs $a$")
    plt.xlim(0, 1)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("hw3_p1c_chernoff.png", dpi=200)


def helstrom_pc_from_trace_norm(delta: np.ndarray) -> float:
    """
    Equal-prior binary discrimination success:
    Pc = 1/2 * (1 + 1/2 ||rho0 - rho1||_1).
    """
    singular_values = np.linalg.svd(delta, compute_uv=False)
    trace_norm = float(np.sum(np.abs(singular_values)))
    return 0.5 * (1.0 + 0.5 * trace_norm)


def pc_problem2_unentangled(p: float) -> float:
    """
    Problem 2(a), probe rho = |+><+|.
    N(rho) = (1-p)rho + p ZrhoZ
    M(rho) = (1-p)rho + p I/2
    """
    plus = ket_plus()
    minus = np.array([1.0, -1.0], dtype=float) / np.sqrt(2.0)
    rho_plus = density_from_ket(plus)
    rho_minus = density_from_ket(minus)
    identity_2 = np.eye(2)

    rho_n = (1.0 - p) * rho_plus + p * rho_minus
    rho_m = (1.0 - p) * rho_plus + 0.5 * p * identity_2
    return helstrom_pc_from_trace_norm(rho_n - rho_m)


def pc_problem2_entangled(p: float) -> float:
    """
    Problem 2(b), ancilla-assisted probe rho = |Phi+><Phi+| on 2 qubits.
    Channel acts on the first qubit only.
    """
    phi_plus = np.array([1.0, 0.0, 0.0, 1.0], dtype=float) / np.sqrt(2.0)
    phi_minus = np.array([1.0, 0.0, 0.0, -1.0], dtype=float) / np.sqrt(2.0)
    rho_phi_plus = density_from_ket(phi_plus)
    rho_phi_minus = density_from_ket(phi_minus)
    identity_4 = np.eye(4)

    # (N ⊗ I)(rho_phi_plus)
    rho_n = (1.0 - p) * rho_phi_plus + p * rho_phi_minus
    # (M ⊗ I)(rho_phi_plus) = (1-p) rho_phi_plus + p * I_4 / 4
    rho_m = (1.0 - p) * rho_phi_plus + 0.25 * p * identity_4
    return helstrom_pc_from_trace_norm(rho_n - rho_m)


def plot_problem2_pc_vs_p(p_grid: np.ndarray) -> None:
    pc_un = [pc_problem2_unentangled(p) for p in p_grid]
    pc_en = [pc_problem2_entangled(p) for p in p_grid]

    plt.figure(figsize=(8, 5))
    plt.plot(p_grid, pc_un, linewidth=2, label="unentangled probe |+><+|")
    plt.plot(p_grid, pc_en, linewidth=2, label="entangled probe |Phi+><Phi+|")
    plt.xlabel("p")
    plt.ylabel(r"$P_c$")
    plt.title(r"Problem 2: Channel Discrimination $P_c$ vs $p$")
    plt.xlim(0, 1)
    plt.ylim(0.5, 1.0)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("hw3_p2_pc_vs_p.png", dpi=200)


def qfunc(x: np.ndarray | float) -> np.ndarray | float:
    """Gaussian tail probability Q(x) = 0.5 * erfc(x / sqrt(2))."""
    return 0.5 - 0.5 * np.vectorize(lambda t: np.math.erf(t / np.sqrt(2.0)))(x)


def qi_locc_roc_gaussian(
    eta: float, lam: float, d: float, n_copies: int, entangled: bool
) -> tuple[np.ndarray, np.ndarray]:
    """
    Problem 3(a): Gaussian-approx ROC for LOCC QI.

    We use a normalized test statistic T ~ N(mu_i, 1) under hypothesis Hi.
    The mean shift scales with sqrt(N * SNR), where entanglement gives d-fold SNR.
    """
    snr_per_copy = eta * lam * (d if entangled else 1.0)
    mu0 = 0.0
    mu1 = np.sqrt(max(n_copies * snr_per_copy, 0.0))

    # Sweep thresholds over a wide enough range to cover ROC corners.
    tmin = min(mu0, mu1) - 6.0
    tmax = max(mu0, mu1) + 6.0
    thresholds = np.linspace(tmin, tmax, 1200)

    pf = qfunc(thresholds - mu0)
    pd = qfunc(thresholds - mu1)
    return np.asarray(pf), np.asarray(pd)


def plot_problem3a_roc_locc(eta: float, lam: float, d: float, n_copies: int = 100) -> None:
    pf_un, pd_un = qi_locc_roc_gaussian(eta, lam, d, n_copies=n_copies, entangled=False)
    pf_en, pd_en = qi_locc_roc_gaussian(eta, lam, d, n_copies=n_copies, entangled=True)

    plt.figure(figsize=(8, 6))
    plt.plot(pf_un, pd_un, linewidth=2, label=f"LOCC unentangled (N={n_copies})")
    plt.plot(pf_en, pd_en, linewidth=2, label=f"LOCC entangled (N={n_copies})")
    plt.plot([0, 1], [0, 1], "k--", alpha=0.5, label="random guess")
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.xlabel(r"$P_f$")
    plt.ylabel(r"$P_d$")
    plt.title("Problem 3(a): LOCC ROC via Gaussian Approximation")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("hw3_p3a_locc_roc.png", dpi=200)


def qi_chernoff_distances(eta: float, lam: float, d: float) -> dict[str, float]:
    """
    Problem 3(b): per-copy Chernoff distances.

    Classical (LOCC) Gaussian model with unit variance:
      C_classical = SNR / 8.
    Quantum counterpart is modeled as a 3 dB gain over LOCC:
      C_quantum = SNR / 4.
    """
    snr_un = eta * lam
    snr_en = eta * lam * d
    return {
        "Cq_un": snr_un / 4.0,
        "Cq_en": snr_en / 4.0,
        "Cc_un_locc": snr_un / 8.0,
        "Cc_en_locc": snr_en / 8.0,
    }


def plot_problem3b_chernoff_bounds(eta: float, lam: float, d: float, n_max: int = 300) -> None:
    dists = qi_chernoff_distances(eta, lam, d)
    n_vals = np.arange(1, n_max + 1, dtype=float)

    pe_cq_un = 0.5 * np.exp(-n_vals * dists["Cq_un"])
    pe_cq_en = 0.5 * np.exp(-n_vals * dists["Cq_en"])
    pe_cc_un = 0.5 * np.exp(-n_vals * dists["Cc_un_locc"])
    pe_cc_en = 0.5 * np.exp(-n_vals * dists["Cc_en_locc"])

    plt.figure(figsize=(8, 6))
    plt.semilogy(n_vals, pe_cq_un, linewidth=2, label=r"quantum Chernoff (unentangled)")
    plt.semilogy(n_vals, pe_cq_en, linewidth=2, label=r"quantum Chernoff (entangled)")
    plt.semilogy(n_vals, pe_cc_un, "--", linewidth=2, label=r"classical LOCC Chernoff (unentangled)")
    plt.semilogy(n_vals, pe_cc_en, "--", linewidth=2, label=r"classical LOCC Chernoff (entangled)")
    plt.xlabel("N")
    plt.ylabel(r"$P_e$ upper bound")
    plt.title("Problem 3(b): Chernoff-Bound Error Exponents")
    plt.grid(alpha=0.3, which="both")
    plt.legend()
    plt.tight_layout()
    plt.savefig("hw3_p3b_chernoff_bounds.png", dpi=200)


def helstrom_projectors_equal_prior(rho0: np.ndarray, rho1: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Equal-prior Helstrom measurement:
      Pi0 projects onto positive eigenspace of (rho0 - rho1),
      Pi1 = I - Pi0.
    """
    delta = rho0 - rho1
    eigvals, eigvecs = np.linalg.eigh(delta)
    pi0 = np.zeros_like(delta, dtype=float)
    for i, val in enumerate(eigvals):
        if val > 1e-12:
            v = eigvecs[:, i]
            pi0 += np.outer(v, v)
    identity = np.eye(delta.shape[0])
    pi1 = identity - pi0
    return pi0, pi1


def optimal_threshold_from_lrt(n_copies: int, q0: float, q1: float) -> int:
    """
    Return smallest k such that log-likelihood ratio >= 0:
      log P(K=k|H1) - log P(K=k|H0) >= 0.
    """
    eps = 1e-12
    q0 = float(np.clip(q0, eps, 1.0 - eps))
    q1 = float(np.clip(q1, eps, 1.0 - eps))

    for k in range(n_copies + 1):
        llr = k * np.log(q1 / q0) + (n_copies - k) * np.log((1.0 - q1) / (1.0 - q0))
        if llr >= 0.0:
            return k
    return n_copies + 1


def simulate_local_optimal_pc(a: float, n_copies: int, n_trials: int, rng: np.random.Generator) -> float:
    """
    Problem 4(a): local protocol via simulation.
    - Apply optimal single-copy POVM to each copy
    - Sum binary outcomes K
    - Use optimal threshold K >= tau to decide H1
    """
    rho0 = density_from_ket(ket_plus())
    rho1 = density_from_ket(ket_psi(a))
    _, pi1 = helstrom_projectors_equal_prior(rho0, rho1)

    # Binary "1" outcome probability under each hypothesis.
    q0 = float(np.trace(pi1 @ rho0))
    q1 = float(np.trace(pi1 @ rho1))
    tau = optimal_threshold_from_lrt(n_copies, q0, q1)

    h = rng.integers(0, 2, size=n_trials)  # 0 or 1 equiprobable
    probs_one = np.where(h == 0, q0, q1)
    k = rng.binomial(n_copies, probs_one)
    decisions = (k >= tau).astype(int)
    return float(np.mean(decisions == h))


def pc_unanimity_protocol(a: float, n_copies: int) -> float:
    """
    Problem 4(b): unanimity protocol (closed form).
    For pure-state overlap s = |<psi0|psi1>|^2:
      Pe = 0.5 * s^N, hence Pc = 1 - 0.5 * s^N.
    """
    s = overlap_squared(a)
    return float(1.0 - 0.5 * (s ** n_copies))


def plot_problem4_pc_vs_a() -> None:
    a_values = np.arange(0.1, 1.0, 0.1)
    ns = [5, 10]
    rng = np.random.default_rng(42)
    n_trials = 20000

    plt.figure(figsize=(8, 6))
    for n_copies in ns:
        pcs_local = [simulate_local_optimal_pc(a, n_copies, n_trials, rng) for a in a_values]
        pcs_unanimity = [pc_unanimity_protocol(a, n_copies) for a in a_values]
        plt.plot(a_values, pcs_local, "o-", linewidth=2, label=f"local optimal sim (N={n_copies})")
        plt.plot(a_values, pcs_unanimity, "s--", linewidth=2, label=f"unanimity closed-form (N={n_copies})")

    plt.xlabel("a")
    plt.ylabel(r"$P_c$")
    plt.title(r"Problem 4: Multi-copy Discrimination, $P_c$ vs $a$")
    plt.xlim(0.1, 0.9)
    plt.ylim(0.5, 1.0)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("hw3_p4_pc_vs_a.png", dpi=200)


def swap_accept_prob_from_overlap_sq(overlap_sq: float) -> float:
    """Single SWAP-test acceptance probability for pure states."""
    return 0.5 * (1.0 + overlap_sq)


def plot_problem5a_swap_observable() -> None:
    """
    Problem 5(a): estimate |<psi|phi>|^2 using SWAP-test simulation.
    psi = |Phi+>, phi = |+> ⊗ |->
    """
    phi_plus = np.array([1.0, 0.0, 0.0, 1.0], dtype=float) / np.sqrt(2.0)
    ket_minus = np.array([1.0, -1.0], dtype=float) / np.sqrt(2.0)
    phi = np.kron(ket_plus(), ket_minus)
    true_overlap_sq = float(np.abs(np.vdot(phi_plus, phi)) ** 2)

    rng = np.random.default_rng(7)
    n_values = np.arange(10, 201, 10)
    est_vals = []
    p_accept = swap_accept_prob_from_overlap_sq(true_overlap_sq)
    for n_copies in n_values:
        accepts = rng.binomial(1, p_accept, size=n_copies)
        p_hat = float(np.mean(accepts))
        est_vals.append(max(0.0, min(1.0, 2.0 * p_hat - 1.0)))

    plt.figure(figsize=(8, 5))
    plt.plot(n_values, [true_overlap_sq] * len(n_values), "k--", linewidth=2, label="true overlap")
    plt.plot(n_values, est_vals, "o-", linewidth=2, label="SWAP-test estimate")
    plt.xlabel("number of state-pair copies N")
    plt.ylabel(r"$|\langle \psi | \phi \rangle|^2$")
    plt.title("Problem 5(a): SWAP-Observable Estimation")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("hw3_p5a_swap_observable.png", dpi=200)


def equality_declaring_probability(a: float, n_copies: int) -> float:
    """
    Problem 5(b): probability of declaring equality using N SWAP tests.
    Declare equality only if all N SWAP tests accept.
    """
    s = overlap_squared(a)
    p_single_accept = swap_accept_prob_from_overlap_sq(s)
    return float(p_single_accept ** n_copies)


def plot_problem5b_equality_test() -> None:
    a_values = np.arange(0.1, 1.0, 0.1)
    ns = [5, 10]

    plt.figure(figsize=(8, 5))
    for n_copies in ns:
        pe_vals = [equality_declaring_probability(a, n_copies) for a in a_values]
        plt.plot(a_values, pe_vals, "o-", linewidth=2, label=f"N={n_copies}")
    plt.xlabel("a")
    plt.ylabel(r"$P_e$ (declare equality)")
    plt.title("Problem 5(b): Equality Test")
    plt.xlim(0.1, 0.9)
    plt.ylim(0, 1)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("hw3_p5b_equality_test.png", dpi=200)


def purity_tr_rho_sq(a: float) -> float:
    """
    For rho = a|+><+| + (1-a)|-><-|, with orthogonal components:
    Tr(rho^2) = a^2 + (1-a)^2.
    """
    return float(a * a + (1.0 - a) * (1.0 - a))


def purity_declaring_probability(a: float, n_copies: int) -> float:
    """
    Problem 5(c): probability of declaring purity with N copies of rho⊗2.
    Single-copy acceptance of SWAP purity test is (1 + Tr(rho^2))/2.
    """
    p_single_accept = 0.5 * (1.0 + purity_tr_rho_sq(a))
    return float(p_single_accept ** n_copies)


def plot_problem5c_purity_test() -> None:
    a_values = np.arange(0.1, 1.0, 0.1)
    ns = [5, 10]

    plt.figure(figsize=(8, 5))
    for n_copies in ns:
        pe_vals = [purity_declaring_probability(a, n_copies) for a in a_values]
        plt.plot(a_values, pe_vals, "o-", linewidth=2, label=f"N={n_copies}")
    plt.xlabel("a")
    plt.ylabel(r"$P_e$ (declare pure)")
    plt.title("Problem 5(c): Purity Test")
    plt.xlim(0.1, 0.9)
    plt.ylim(0, 1)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("hw3_p5c_purity_test.png", dpi=200)


def product_state_reduced_purity(a: float) -> float:
    """
    For |psi>_AB = sqrt(a)|00> + sqrt(1-a)|11>, reduced purity is:
    Tr(rho_A^2) = Tr(rho_B^2) = a^2 + (1-a)^2.
    """
    return float(a * a + (1.0 - a) * (1.0 - a))


def product_declaring_probability(a: float, n_copies: int) -> float:
    """
    Problem 5(d): product test declaring separability.
    For bipartite pure states, single-copy product-test acceptance:
    p_accept = (1 + Tr(rho_A^2)) / 2.
    """
    p_single_accept = 0.5 * (1.0 + product_state_reduced_purity(a))
    return float(p_single_accept ** n_copies)


def plot_problem5d_product_test() -> None:
    a_values = np.arange(0.1, 1.0, 0.1)
    ns = [5, 10]

    plt.figure(figsize=(8, 5))
    for n_copies in ns:
        pe_vals = [product_declaring_probability(a, n_copies) for a in a_values]
        plt.plot(a_values, pe_vals, "o-", linewidth=2, label=f"N={n_copies}")
    plt.xlabel("a")
    plt.ylabel(r"$P_e$ (declare separable)")
    plt.title("Problem 5(d): Product Test")
    plt.xlim(0.1, 0.9)
    plt.ylim(0, 1)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("hw3_p5d_product_test.png", dpi=200)


def parse_problem_selection(only: str | None) -> set[int]:
    """Parse comma-separated problem indices, defaulting to all 1..5."""
    if only is None or only.strip() == "":
        return {1, 2, 3, 4, 5}
    parts = [p.strip() for p in only.split(",") if p.strip()]
    selected = set()
    for part in parts:
        idx = int(part)
        if idx < 1 or idx > 5:
            raise ValueError("Problem indices must be in {1,2,3,4,5}.")
        selected.add(idx)
    if not selected:
        raise ValueError("No valid problem indices provided.")
    return selected


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate plots for ELEN E6730 HW3 problems."
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated problem numbers to run, e.g. '1,3,5'. Default: all.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Save figures without opening plot windows.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Directory where output figures are saved. Default: current directory.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    selected = parse_problem_selection(args.only)

    os.makedirs(args.output_dir, exist_ok=True)
    os.chdir(args.output_dir)

    a_grid = np.linspace(0.0, 1.0, 501)
    p_grid = np.linspace(0.0, 1.0, 501)
    eta = 0.4
    lam = 0.1
    d = 4.0
    if 1 in selected:
        plot_pc_vs_a(a_grid)
        plot_roc_curves()
        plot_chernoff_vs_a(a_grid)
    if 2 in selected:
        plot_problem2_pc_vs_p(p_grid)
    if 3 in selected:
        plot_problem3a_roc_locc(eta, lam, d, n_copies=100)
        plot_problem3b_chernoff_bounds(eta, lam, d, n_max=300)
    if 4 in selected:
        plot_problem4_pc_vs_a()
    if 5 in selected:
        plot_problem5a_swap_observable()
        plot_problem5b_equality_test()
        plot_problem5c_purity_test()
        plot_problem5d_product_test()

    if args.no_show:
        plt.close("all")
    else:
        plt.show()


if __name__ == "__main__":
    main()
