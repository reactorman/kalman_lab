import argparse
import math
import os
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages


# -------- shared helpers --------
def overlap_sq_plus_vs_psi(a: float) -> float:
    """|<+|psi(a)>|^2 for |psi(a)> = sqrt(a)|0> + sqrt(1-a)|1>."""
    return 0.5 * (1.0 + 2.0 * math.sqrt(max(a * (1.0 - a), 0.0)))


def savefig_current(name: str) -> None:
    plt.tight_layout()
    plt.savefig(name, dpi=200)


# -------- plotters: draw on an Axes (same content as before) --------
def plot_p1a_on(ax: Any, a_grid: np.ndarray) -> None:
    for pi0 in [0.1, 0.2, 0.3, 0.4, 0.5]:
        pi1 = 1.0 - pi0
        pcs = []
        for a in a_grid:
            s = overlap_sq_plus_vs_psi(float(a))
            pcs.append(0.5 * (1.0 + math.sqrt(max(1.0 - 4.0 * pi0 * pi1 * s, 0.0))))
        ax.plot(a_grid, pcs, label=rf"$\pi_0={pi0:.1f}$")
    ax.set_xlabel("a")
    ax.set_ylabel(r"$P_c$")
    ax.set_title(r"Problem 1(a): Optimal $P_c$ vs $a$")
    ax.set_xlim(0, 1)
    ax.set_ylim(0.5, 1.0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def plot_p1b_on(ax: Any) -> None:
    plus = np.array([1.0, 1.0], dtype=float) / math.sqrt(2.0)
    thetas = np.linspace(0.0, math.pi, 4000, endpoint=False)
    for a in [0.1, 0.2, 0.3, 0.4, 0.5]:
        psi = np.array([math.sqrt(a), math.sqrt(1.0 - a)], dtype=float)
        pfs = np.empty_like(thetas)
        pds = np.empty_like(thetas)
        for i, th in enumerate(thetas):
            e1 = np.array([math.cos(float(th)), math.sin(float(th))], dtype=float)
            pfs[i] = abs(np.vdot(e1, plus)) ** 2
            pds[i] = abs(np.vdot(e1, psi)) ** 2
        idx = np.argsort(pfs)
        pfs = pfs[idx]
        pds = pds[idx]
        ax.plot(pfs, pds, label=f"a={a:.1f}")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="random guess")
    ax.set_xlabel(r"$P_f$")
    ax.set_ylabel(r"$P_d$")
    ax.set_title("Problem 1(b): Quantum ROC Curves")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def plot_p1c_on(ax: Any, a_grid: np.ndarray) -> None:
    cvals = [-math.log(max(overlap_sq_plus_vs_psi(float(a)), 1e-15)) for a in a_grid]
    ax.plot(a_grid, cvals, linewidth=2)
    ax.set_xlabel("a")
    ax.set_ylabel(r"$C(\rho_0,\rho_1)$")
    ax.set_title(r"Problem 1(c): Quantum Chernoff Distance vs $a$")
    ax.set_xlim(0, 1)
    ax.grid(alpha=0.3)


def compute_problem2_curves(
    p_grid: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    plus = np.array([1.0, 1.0], dtype=float) / math.sqrt(2.0)
    minus = np.array([1.0, -1.0], dtype=float) / math.sqrt(2.0)
    rho_plus = np.outer(plus, plus)
    rho_minus = np.outer(minus, minus)
    i2 = np.eye(2)

    phi_plus = np.array([1.0, 0.0, 0.0, 1.0], dtype=float) / math.sqrt(2.0)
    phi_minus = np.array([1.0, 0.0, 0.0, -1.0], dtype=float) / math.sqrt(2.0)
    rho_phi_plus = np.outer(phi_plus, phi_plus)
    rho_phi_minus = np.outer(phi_minus, phi_minus)
    i4 = np.eye(4)

    def helstrom_pc_from_delta(delta: np.ndarray) -> float:
        svals = np.linalg.svd(delta, compute_uv=False)
        tr_norm = float(np.sum(np.abs(svals)))
        return 0.5 * (1.0 + 0.5 * tr_norm)

    pc_un: list[float] = []
    pc_en: list[float] = []
    for p in p_grid:
        rho_n = (1.0 - p) * rho_plus + p * rho_minus
        rho_m = (1.0 - p) * rho_plus + 0.5 * p * i2
        pc_un.append(helstrom_pc_from_delta(rho_n - rho_m))

        rho_n2 = (1.0 - p) * rho_phi_plus + p * rho_phi_minus
        rho_m2 = (1.0 - p) * rho_phi_plus + 0.25 * p * i4
        pc_en.append(helstrom_pc_from_delta(rho_n2 - rho_m2))

    return p_grid, np.asarray(pc_un), np.asarray(pc_en)


def plot_p2_on(ax: Any, p_grid: np.ndarray, pc_un: np.ndarray, pc_en: np.ndarray) -> None:
    ax.plot(p_grid, pc_un, linewidth=2, label="unentangled probe |+><+|")
    ax.plot(p_grid, pc_en, linewidth=2, label="entangled probe |Phi+><Phi+|")
    ax.set_xlabel("p")
    ax.set_ylabel(r"$P_c$")
    ax.set_title(r"Problem 2: Channel Discrimination $P_c$ vs $p$")
    ax.set_xlim(0, 1)
    ax.set_ylim(0.5, 1.0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def plot_p3a_on(ax: Any, eta: float, lam: float, d: float, n: int) -> None:
    for entangled, label in [
        (False, f"LOCC unentangled (N={n})"),
        (True, f"LOCC entangled (N={n})"),
    ]:
        snr = eta * lam * (d if entangled else 1.0)
        mu0, mu1 = 0.0, math.sqrt(n * snr)
        taus = np.linspace(-6.0, mu1 + 6.0, 1200)
        erf_vec = np.vectorize(lambda t: math.erf(float(t) / math.sqrt(2.0)))
        pf = 0.5 - 0.5 * erf_vec(taus - mu0)
        pd = 0.5 - 0.5 * erf_vec(taus - mu1)
        ax.plot(pf, pd, linewidth=2, label=label)
    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="random guess")
    ax.set_xlabel(r"$P_f$")
    ax.set_ylabel(r"$P_d$")
    ax.set_title("Problem 3(a): LOCC ROC via Gaussian Approximation")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)


def plot_p3b_on(ax: Any, eta: float, lam: float, d: float) -> None:
    n_vals = np.arange(1, 301, dtype=float)
    snr_un = eta * lam
    snr_en = eta * lam * d
    c_q_un, c_q_en = snr_un / 4.0, snr_en / 4.0
    c_c_un, c_c_en = snr_un / 8.0, snr_en / 8.0
    ax.semilogy(n_vals, 0.5 * np.exp(-n_vals * c_q_un), linewidth=2, label="quantum Chernoff (unentangled)")
    ax.semilogy(n_vals, 0.5 * np.exp(-n_vals * c_q_en), linewidth=2, label="quantum Chernoff (entangled)")
    ax.semilogy(n_vals, 0.5 * np.exp(-n_vals * c_c_un), "--", linewidth=2, label="classical LOCC Chernoff (unentangled)")
    ax.semilogy(n_vals, 0.5 * np.exp(-n_vals * c_c_en), "--", linewidth=2, label="classical LOCC Chernoff (entangled)")
    ax.set_xlabel("N")
    ax.set_ylabel(r"$P_e$ upper bound")
    ax.set_title("Problem 3(b): Chernoff-Bound Error Exponents")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=7)


def plot_p4_on(ax: Any) -> None:
    a_values = np.arange(0.1, 1.0, 0.1)
    rng = np.random.default_rng(42)
    n_trials = 20000
    plus = np.array([1.0, 1.0], dtype=float) / math.sqrt(2.0)
    rho0 = np.outer(plus, plus)

    for n in [5, 10]:
        pcs_local = []
        pcs_unanimity = []
        for a in a_values:
            psi = np.array([math.sqrt(a), math.sqrt(1.0 - a)], dtype=float)
            rho1 = np.outer(psi, psi)

            delta = rho0 - rho1
            evals, evecs = np.linalg.eigh(delta)
            pi1 = np.zeros((2, 2), dtype=float)
            for i, ev in enumerate(evals):
                if ev < -1e-12:
                    v = evecs[:, i]
                    pi1 += np.outer(v, v)
            q0 = float(np.trace(pi1 @ rho0))
            q1 = float(np.trace(pi1 @ rho1))
            q0 = float(np.clip(q0, 1e-12, 1.0 - 1e-12))
            q1 = float(np.clip(q1, 1e-12, 1.0 - 1e-12))

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

            s = overlap_sq_plus_vs_psi(float(a))
            pcs_unanimity.append(1.0 - 0.5 * (s ** n))

        ax.plot(a_values, pcs_local, "o-", linewidth=2, label=f"local optimal sim (N={n})")
        ax.plot(a_values, pcs_unanimity, "s--", linewidth=2, label=f"unanimity closed-form (N={n})")

    ax.set_xlabel("a")
    ax.set_ylabel(r"$P_c$")
    ax.set_title(r"Problem 4: Multi-copy Discrimination, $P_c$ vs $a$")
    ax.set_xlim(0.1, 0.9)
    ax.set_ylim(0.5, 1.0)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def plot_p5a_on(ax: Any) -> None:
    phi_plus = np.array([1.0, 0.0, 0.0, 1.0], dtype=float) / math.sqrt(2.0)
    plus = np.array([1.0, 1.0], dtype=float) / math.sqrt(2.0)
    minus = np.array([1.0, -1.0], dtype=float) / math.sqrt(2.0)
    phi = np.kron(plus, minus)
    true_overlap = float(abs(np.vdot(phi_plus, phi)) ** 2)
    p_accept = 0.5 * (1.0 + true_overlap)
    rng = np.random.default_rng(7)
    n_values = np.arange(10, 201, 10)
    est = []
    for n in n_values:
        acc = rng.binomial(1, p_accept, size=n)
        est.append(float(np.clip(2.0 * np.mean(acc) - 1.0, 0.0, 1.0)))
    ax.plot(n_values, [true_overlap] * len(n_values), "k--", linewidth=2, label="true overlap")
    ax.plot(n_values, est, "o-", linewidth=2, label="SWAP-test estimate")
    ax.set_xlabel("number of state-pair copies N")
    ax.set_ylabel(r"$|\langle \psi | \phi \rangle|^2$")
    ax.set_title("Problem 5(a): SWAP-Observable Estimation")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def plot_p5bcd_on(ax: Any, part: str, a_values: np.ndarray, ns: list[int]) -> None:
    titles = {
        "b": ("Problem 5(b): Equality Test", r"$P_e$ (declare equality)", lambda a: 0.5 * (1.0 + overlap_sq_plus_vs_psi(float(a)))),
        "c": ("Problem 5(c): Purity Test", r"$P_e$ (declare pure)", lambda a: 0.5 * (1.0 + a * a + (1.0 - a) * (1.0 - a))),
        "d": ("Problem 5(d): Product Test", r"$P_e$ (declare separable)", lambda a: 0.5 * (1.0 + a * a + (1.0 - a) * (1.0 - a))),
    }
    title, ylabel, p_accept_fn = titles[part]
    for n in ns:
        vals = [p_accept_fn(a) ** n for a in a_values]
        ax.plot(a_values, vals, "o-", linewidth=2, label=f"N={n}")
    ax.set_xlabel("a")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xlim(0.1, 0.9)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)


def save_panel_pngs(
    a_grid: np.ndarray,
    p_grid: np.ndarray,
    pc_un: np.ndarray,
    pc_en: np.ndarray,
    eta: float,
    lam: float,
    d: float,
) -> None:
    n_qi = 100
    # Page A: 1a, 1b, 1c, 2
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    plot_p1a_on(axes[0, 0], a_grid)
    plot_p1b_on(axes[0, 1])
    plot_p1c_on(axes[1, 0], a_grid)
    plot_p2_on(axes[1, 1], p_grid, pc_un, pc_en)
    fig.suptitle("Problems 1(a–c) and 2", fontsize=14, y=1.02)
    savefig_current("hw3_panel_p1_p2.png")
    plt.close(fig)

    # Page B: 3a, 3b, 4 (+ empty fourth cell)
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    plot_p3a_on(axes[0, 0], eta, lam, d, n_qi)
    plot_p3b_on(axes[0, 1], eta, lam, d)
    plot_p4_on(axes[1, 0])
    axes[1, 1].set_visible(False)
    fig.suptitle("Problems 3(a–b) and 4", fontsize=14, y=1.02)
    savefig_current("hw3_panel_p3_p4.png")
    plt.close(fig)

    # Page C: 5a–d
    a_values = np.arange(0.1, 1.0, 0.1)
    ns = [5, 10]
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    plot_p5a_on(axes[0, 0])
    plot_p5bcd_on(axes[0, 1], "b", a_values, ns)
    plot_p5bcd_on(axes[1, 0], "c", a_values, ns)
    plot_p5bcd_on(axes[1, 1], "d", a_values, ns)
    fig.suptitle("Problem 5 (a–d)", fontsize=14, y=1.02)
    savefig_current("hw3_panel_p5.png")
    plt.close(fig)


def save_multipage_pdf(
    path: str,
    a_grid: np.ndarray,
    p_grid: np.ndarray,
    pc_un: np.ndarray,
    pc_en: np.ndarray,
    eta: float,
    lam: float,
    d: float,
) -> None:
    n_qi = 100
    a_values = np.arange(0.1, 1.0, 0.1)
    ns = [5, 10]
    with PdfPages(path) as pdf:
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        plot_p1a_on(axes[0, 0], a_grid)
        plot_p1b_on(axes[0, 1])
        plot_p1c_on(axes[1, 0], a_grid)
        plot_p2_on(axes[1, 1], p_grid, pc_un, pc_en)
        fig.suptitle("Problems 1(a–c) and 2", fontsize=12, y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        pdf.savefig(fig)
        plt.close(fig)

        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        plot_p3a_on(axes[0, 0], eta, lam, d, n_qi)
        plot_p3b_on(axes[0, 1], eta, lam, d)
        plot_p4_on(axes[1, 0])
        axes[1, 1].set_visible(False)
        fig.suptitle("Problems 3(a–b) and 4", fontsize=12, y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        pdf.savefig(fig)
        plt.close(fig)

        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        plot_p5a_on(axes[0, 0])
        plot_p5bcd_on(axes[0, 1], "b", a_values, ns)
        plot_p5bcd_on(axes[1, 0], "c", a_values, ns)
        plot_p5bcd_on(axes[1, 1], "d", a_values, ns)
        fig.suptitle("Problem 5 (a–d)", fontsize=12, y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        pdf.savefig(fig)
        plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ELEN E6730 HW3 plotting script.")
    parser.add_argument("--only", type=str, default="", help="Comma-separated problem ids, e.g. 1,3,5")
    parser.add_argument("--no-show", action="store_true", help="Save figures without opening windows")
    parser.add_argument("--output-dir", type=str, default=".", help="Directory for output figures")
    parser.add_argument(
        "--no-panel-png",
        action="store_true",
        help="Skip combined panel PNGs (hw3_panel_*.png).",
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default="hw3_all.pdf",
        help="Multi-page PDF path (4 plots on pages 1 and 3; page 2 has 3 plots). Set empty to skip.",
    )
    parser.add_argument("--no-pdf", action="store_true", help="Do not write the combined PDF.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    os.chdir(args.output_dir)

    if args.only.strip():
        selected = {int(x.strip()) for x in args.only.split(",") if x.strip()}
    else:
        selected = {1, 2, 3, 4, 5}

    a_grid = np.linspace(0.0, 1.0, 501)
    p_grid = np.linspace(0.0, 1.0, 501)
    eta, lam, d = 0.4, 0.1, 4.0
    p_grid2, pc_un, pc_en = compute_problem2_curves(p_grid)
    n_qi = 100
    all_five = selected == {1, 2, 3, 4, 5}

    if 1 in selected:
        fig, ax = plt.subplots(figsize=(8, 5))
        plot_p1a_on(ax, a_grid)
        savefig_current("hw3_p1a_pc_vs_a.png")
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(8, 6))
        plot_p1b_on(ax)
        savefig_current("hw3_p1b_roc.png")
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(8, 5))
        plot_p1c_on(ax, a_grid)
        savefig_current("hw3_p1c_chernoff.png")
        plt.close(fig)
    if 2 in selected:
        fig, ax = plt.subplots(figsize=(8, 5))
        plot_p2_on(ax, p_grid2, pc_un, pc_en)
        savefig_current("hw3_p2_pc_vs_p.png")
        plt.close(fig)
    if 3 in selected:
        fig, ax = plt.subplots(figsize=(8, 6))
        plot_p3a_on(ax, eta, lam, d, n_qi)
        savefig_current("hw3_p3a_locc_roc.png")
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(8, 6))
        plot_p3b_on(ax, eta, lam, d)
        savefig_current("hw3_p3b_chernoff_bounds.png")
        plt.close(fig)
    if 4 in selected:
        fig, ax = plt.subplots(figsize=(8, 6))
        plot_p4_on(ax)
        savefig_current("hw3_p4_pc_vs_a.png")
        plt.close(fig)
    if 5 in selected:
        fig, ax = plt.subplots(figsize=(8, 5))
        plot_p5a_on(ax)
        savefig_current("hw3_p5a_swap_observable.png")
        plt.close(fig)
        a_values = np.arange(0.1, 1.0, 0.1)
        ns = [5, 10]
        for letter, fn in [
            ("b", "hw3_p5b_equality_test.png"),
            ("c", "hw3_p5c_purity_test.png"),
            ("d", "hw3_p5d_product_test.png"),
        ]:
            fig, ax = plt.subplots(figsize=(8, 5))
            plot_p5bcd_on(ax, letter, a_values, ns)
            savefig_current(fn)
            plt.close(fig)

    if all_five and not args.no_panel_png:
        save_panel_pngs(a_grid, p_grid2, pc_un, pc_en, eta, lam, d)
    if all_five and not args.no_pdf and args.pdf.strip():
        save_multipage_pdf(args.pdf.strip(), a_grid, p_grid2, pc_un, pc_en, eta, lam, d)

    if args.no_show:
        plt.close("all")
    else:
        plt.show()


if __name__ == "__main__":
    main()
