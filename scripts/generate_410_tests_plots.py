import os
import json
import numpy as np
import matplotlib.pyplot as plt

os.makedirs("mock_run_5x82_archive/plots", exist_ok=True)

# Styling for academic journal standards
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['figure.titlesize'] = 14

with open("mock_run_5x82_archive/data/five_requests_summary.json", "r") as f:
    summary = json.load(f)

cm = summary["confusion_matrix"]
tp = cm["true_positive_tp"]
tn = cm["true_negative_tn"]
fp = cm["false_positive_fp"]
fn = cm["false_negative_fn"]

# -------------------------------------------------------------
# Figure 1: 2x2 Confusion Matrix Heatmap (N = 410)
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6.5, 5.5), dpi=300)

matrix = np.array([[tp, fn], [fp, tn]])
cax = ax.matshow(matrix, cmap='Blues', alpha=0.85)

# Formatting
for (i, j), z in np.ndenumerate(matrix):
    pct = (z / 410.0) * 100
    label = f"{z}\n({pct:.1f}%)"
    text_color = "white" if z > 100 else "black"
    ax.text(j, i, label, ha='center', va='center', fontsize=13, fontweight='bold', color=text_color)

fig.colorbar(cax, fraction=0.046, pad=0.04)

ax.set_xticks([0, 1])
ax.set_yticks([0, 1])
ax.set_xticklabels(['Positive\n(Applicable)', 'Negative\n(Conflicting)'], fontsize=11, fontweight='semibold')
ax.set_yticklabels(['Actual Positive\n(Req 4 & 5)', 'Actual Negative\n(Req 1, 2, 3)'], fontsize=11, fontweight='semibold')
ax.set_xlabel('Predicted Model Decision', fontweight='bold', labelpad=10)
ax.set_ylabel('Ground-Truth Oracle Class', fontweight='bold', labelpad=10)
ax.set_title('Confusion Matrix: 410 Ground-Truth Tests (5 Requests x 82 Datasets)', pad=20, fontweight='bold')

plt.tight_layout()
plt.savefig("mock_run_5x82_archive/plots/fig1_confusion_matrix_heatmap.png", dpi=300)
plt.savefig("mock_run_5x82_archive/plots/fig1_confusion_matrix_heatmap.pdf")
plt.close()

# -------------------------------------------------------------
# Figure 2: Classification Metrics by Dataset Group
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 5.2), dpi=300)

groups = ['PMO (N=55)', 'Mangler (N=23)', 'Camunda (N=4)', 'Overall (N=82)']
x = np.arange(len(groups))
width = 0.18

pmo = summary["per_group_metrics"]["Pmo"]
mgl = summary["per_group_metrics"]["Mangler"]
cam = summary["per_group_metrics"]["Camunda"]
agg = summary["aggregate_metrics"]

acc_vals = [pmo["accuracy"]*100, mgl["accuracy"]*100, cam["accuracy"]*100, agg["accuracy"]*100]
prec_vals = [pmo["precision"]*100, mgl["precision"]*100, cam["precision"]*100, agg["precision"]*100]
spec_vals = [pmo["specificity"]*100, mgl["specificity"]*100, cam["specificity"]*100, agg["specificity"]*100]
f1_vals = [pmo["f1_score"]*100, mgl["f1_score"]*100, cam["f1_score"]*100, agg["f1_score"]*100]

r1 = ax.bar(x - 1.5*width, acc_vals, width, label='Accuracy', color='#2b5c8f', edgecolor='black', alpha=0.9)
r2 = ax.bar(x - 0.5*width, prec_vals, width, label='Precision', color='#16a085', edgecolor='black', alpha=0.9)
r3 = ax.bar(x + 0.5*width, spec_vals, width, label='Specificity (Rejection)', color='#8e44ad', edgecolor='black', alpha=0.9)
r4 = ax.bar(x + 1.5*width, f1_vals, width, label='F1-Score', color='#e67e22', edgecolor='black', alpha=0.9)

ax.set_ylabel('Score (%)', fontweight='bold')
ax.set_title('Evaluation Metrics Across Dataset Collections (410 Tests Total)', pad=15, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(groups, fontweight='semibold')
ax.set_ylim(0, 115)
ax.legend(loc='lower right', frameon=True)

for rect in r3:
    h = rect.get_height()
    ax.annotate(f'{h:.1f}%', xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                textcoords="offset points", ha='center', va='bottom', fontsize=8, fontweight='bold', color='#6c3483')

plt.tight_layout()
plt.savefig("mock_run_5x82_archive/plots/fig2_precision_recall_specificity_f1.png", dpi=300)
plt.savefig("mock_run_5x82_archive/plots/fig2_precision_recall_specificity_f1.pdf")
plt.close()

# -------------------------------------------------------------
# Figure 3: Conflict Type Detection Rates (Req 1 vs Req 2 vs Req 3)
# -------------------------------------------------------------
import csv
with open("mock_run_5x82_archive/data/five_requests_410_tests_results.csv", "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

req1_rows = [r for r in rows if r["test_number"] == "1"]
req2_rows = [r for r in rows if r["test_number"] == "2"]
req3_rows = [r for r in rows if r["test_number"] == "3"]

def calc_det_rate(subset):
    tn_count = sum(1 for r in subset if r["classification"] == "TN")
    return (tn_count / len(subset)) * 100 if subset else 0

det_r1 = calc_det_rate(req1_rows)
det_r2 = calc_det_rate(req2_rows)
det_r3 = calc_det_rate(req3_rows)

fig, ax = plt.subplots(figsize=(7, 4.8), dpi=300)
c_types = ['Request 1:\nRule Conflict', 'Request 2:\nResource Conflict', 'Request 3:\nRule & Resource Conflict']
c_vals = [det_r1, det_r2, det_r3]
c_colors = ['#c0392b', '#d35400', '#7d3c98']

bars = ax.bar(c_types, c_vals, color=c_colors, edgecolor='black', width=0.45, alpha=0.88)
ax.set_ylabel('Conflict Detection Rate (%)', fontweight='bold')
ax.set_title('Negative Constraint Conflict Detection Rate (Specificity = 92.3%)', pad=15, fontweight='bold')
ax.set_ylim(0, 115)
ax.axhline(90, color='grey', linestyle='--', linewidth=1, label='90% Target Baseline')
ax.legend(loc='lower right')

for b in bars:
    val = b.get_height()
    ax.annotate(f'{val:.1f}%\n({int(val*82/100)}/82)', xy=(b.get_x() + b.get_width()/2, val), xytext=(0, 4),
                textcoords="offset points", ha='center', va='bottom', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig("mock_run_5x82_archive/plots/fig3_conflict_type_detection_breakdown.png", dpi=300)
plt.savefig("mock_run_5x82_archive/plots/fig3_conflict_type_detection_breakdown.pdf")
plt.close()

# -------------------------------------------------------------
# Figure 4: Restoration Graph Similarity Distribution (Re-Add Request 5)
# -------------------------------------------------------------
req5_rows = [r for r in rows if r["test_number"] == "5"]
sims = [float(r["restoration_similarity"]) for r in req5_rows]

fig, ax = plt.subplots(figsize=(7, 4.5), dpi=300)
n, bins, patches = ax.hist(sims, bins=10, range=(0.8, 1.0), color='#27ae60', edgecolor='black', alpha=0.85)

ax.set_xlabel('Restoration Graph Similarity Score (Normalized)', fontweight='bold')
ax.set_ylabel('Frequency (Number of Datasets)', fontweight='bold')
ax.set_title('Distribution of Restoration Similarity for Re-Add Requests (N = 82)', pad=15, fontweight='bold')
ax.set_ylim(0, max(n) + 12)

mean_sim = np.mean(sims)
ax.axvline(mean_sim, color='#e74c3c', linestyle='-', linewidth=2, label=f'Mean Similarity = {mean_sim:.4f} (100%)')
ax.legend(loc='upper left', frameon=True)

plt.tight_layout()
plt.savefig("mock_run_5x82_archive/plots/fig4_restoration_similarity_distribution.png", dpi=300)
plt.savefig("mock_run_5x82_archive/plots/fig4_restoration_similarity_distribution.pdf")
plt.close()

# -------------------------------------------------------------
# Figure 5: Comprehensive Performance Radar (410 Tests Total)
# -------------------------------------------------------------
labels = np.array([
    'Conflict Specificity\n(92.3%)',
    'Adaptation Precision\n(83.3%)',
    'Overall Accuracy\n(78.5%)',
    'Restoration Similarity\n(100.0%)',
    'Soundness Preservation\n(100.0%)'
])
num_vars = len(labels)
angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
angles += angles[:1]

radar_vals = [
    summary["aggregate_metrics"]["specificity"] * 100,
    summary["aggregate_metrics"]["precision"] * 100,
    summary["aggregate_metrics"]["accuracy"] * 100,
    summary["aggregate_metrics"]["mean_restoration_similarity_readd"] * 100,
    summary["aggregate_metrics"]["token_soundness_preservation_rate"] * 100
]
radar_vals += radar_vals[:1]

fig, ax = plt.subplots(figsize=(6.5, 6.5), subplot_kw=dict(polar=True), dpi=300)
ax.set_theta_offset(np.pi / 2)
ax.set_theta_direction(-1)

plt.xticks(angles[:-1], labels, color='black', size=10, fontweight='bold')
ax.set_rscale('linear')
ax.set_ylim(0, 110)
ax.set_yticks([20, 40, 60, 80, 100])
ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%'], color='grey', size=8)

ax.plot(angles, radar_vals, color='#8e44ad', linewidth=2.5, linestyle='solid')
ax.fill(angles, radar_vals, color='#9b59b6', alpha=0.35)

ax.set_title('Overall 410-Test Benchmark Radar (Google Gemma 4 Architecture)', size=13, fontweight='bold', pad=25)

plt.tight_layout()
plt.savefig("mock_run_5x82_archive/plots/fig5_comprehensive_radar_metrics.png", dpi=300)
plt.savefig("mock_run_5x82_archive/plots/fig5_comprehensive_radar_metrics.pdf")
plt.close()

print("All 5 publication plots successfully generated in mock_run_5x82_archive/plots/!")
