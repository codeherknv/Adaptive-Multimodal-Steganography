import csv

with open('results/phase10_benchmark_summary.csv', 'r', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

print(f"Total benchmark records: {len(rows)}")

print("\n=== CASES WHERE MARKOWITZ (lambda=0.00) DOES NOT WIN ===")
scenarios = ['Scenario 1 (Balanced)', 'Scenario 2 (Asymmetric Video-Dominant)', 'Scenario 3 (Asymmetric Audio-Dominant)']
payload_levels = ['Low', 'Medium', 'High', 'Near-Cap (90%)']

for scen in scenarios:
    print(f"\n--- {scen} ---")
    for p_lev in payload_levels:
        subset = [r for r in rows if r['scenario'] == scen and r['payload_level'] == p_lev]
        m0 = next(r for r in subset if r['strategy'] == 'Portfolio (lambda=0.00)')
        
        best_img = max(subset, key=lambda r: float(r['image_psnr_db']))
        best_aud = max(subset, key=lambda r: float(r['audio_snr_db']))
        best_vid = max(subset, key=lambda r: float(r['video_psnr_db']))
        best_risk = min(subset, key=lambda r: float(r['modeled_risk_proxy']))

        print(f"\n[{p_lev} Payload: {m0['actual_bytes']}B]")
        if best_img['strategy'] != m0['strategy']:
            print(f"  * Image PSNR: {best_img['strategy']} won with {best_img['image_psnr_db']} dB (M0 had {m0['image_psnr_db']} dB)")
        else:
            print(f"  * Image PSNR: M0 won with {m0['image_psnr_db']} dB")

        if best_aud['strategy'] != m0['strategy']:
            print(f"  * Audio SNR:  {best_aud['strategy']} won with {best_aud['audio_snr_db']} dB (M0 had {m0['audio_snr_db']} dB)")
        else:
            print(f"  * Audio SNR:  M0 won with {m0['audio_snr_db']} dB")

        if best_vid['strategy'] != m0['strategy']:
            print(f"  * Video PSNR: {best_vid['strategy']} won with {best_vid['video_psnr_db']} dB (M0 had {m0['video_psnr_db']} dB)")
        else:
            print(f"  * Video PSNR: M0 won with {m0['video_psnr_db']} dB")

        if best_risk['strategy'] != m0['strategy']:
            print(f"  * Risk Proxy: {best_risk['strategy']} won with {best_risk['modeled_risk_proxy']} (M0 had {m0['modeled_risk_proxy']})")
        else:
            print(f"  * Risk Proxy: M0 won with {m0['modeled_risk_proxy']}")

print("\n=== CONCENTRATION RISK FLAGS (>90% IN ONE CARRIER) ===")
conc = [r for r in rows if r['concentrated_over_90pct'] == 'True']
for r in conc:
    sh = max(float(r['share_image_pct']), float(r['share_audio_pct']), float(r['share_video_pct']))
    print(f"[{r['scenario']} | {r['payload_level']}] {r['strategy']}: {r['concentrated_carrier'].upper()} absorbed {sh:.1f}% of payload")

print("\n=== ABLATION: MARKOWITZ (DIAGONAL SIGMA) vs ADAPTIVE vs CAPACITY PROPORTIONAL ===")
for scen in scenarios:
    print(f"\n--- {scen} (Medium Payload) ---")
    subset = [r for r in rows if r['scenario'] == scen and r['payload_level'] == 'Medium']
    adp = next(r for r in subset if r['strategy'] == 'Adaptive Feature')
    cp = next(r for r in subset if r['strategy'] == 'Capacity-Proportional')
    m0 = next(r for r in subset if r['strategy'] == 'Portfolio (lambda=0.00)')
    m5 = next(r for r in subset if r['strategy'] == 'Portfolio (lambda=0.50)')
    m1 = next(r for r in subset if r['strategy'] == 'Portfolio (lambda=1.00)')

    print(f"  Capacity-Proportional: Allocs=[{cp['b_image']}B, {cp['b_audio']}B, {cp['b_video']}B] | Risk={float(cp['modeled_risk_proxy']):.2e} | Aud SNR={cp['audio_snr_db']}dB | Img PSNR={cp['image_psnr_db']}dB")
    print(f"  Adaptive Feature:      Allocs=[{adp['b_image']}B, {adp['b_audio']}B, {adp['b_video']}B] | Risk={float(adp['modeled_risk_proxy']):.2e} | Aud SNR={adp['audio_snr_db']}dB | Img PSNR={adp['image_psnr_db']}dB")
    print(f"  Portfolio (lambda=0.0):Allocs=[{m0['b_image']}B, {m0['b_audio']}B, {m0['b_video']}B] | Risk={float(m0['modeled_risk_proxy']):.2e} | Aud SNR={m0['audio_snr_db']}dB | Img PSNR={m0['image_psnr_db']}dB")
    print(f"  Portfolio (lambda=0.5):Allocs=[{m5['b_image']}B, {m5['b_audio']}B, {m5['b_video']}B] | Risk={float(m5['modeled_risk_proxy']):.2e} | Aud SNR={m5['audio_snr_db']}dB | Img PSNR={m5['image_psnr_db']}dB")
    print(f"  Portfolio (lambda=1.0):Allocs=[{m1['b_image']}B, {m1['b_audio']}B, {m1['b_video']}B] | Risk={float(m1['modeled_risk_proxy']):.2e} | Aud SNR={m1['audio_snr_db']}dB | Img PSNR={m1['image_psnr_db']}dB")
