def grade_audit(seo, perf, links):
    score = 0
    # SEO: max 40
    seo_score = max(0, 40 - sum(seo.values()))
    # Performance: max 40
    perf_score = 40 - int((perf['lcp_ms']/4000)*40)
    # Links: max 20
    link_score = 20 - int(links["internal_links_count"]/50*20)
    score = max(0, seo_score + perf_score + link_score)
    grade = "A" if score>=85 else "B" if score>=70 else "C" if score>=50 else "D"
    breakdown = {"seo": seo_score, "performance": perf_score, "links": link_score}
    return score, grade, breakdown
