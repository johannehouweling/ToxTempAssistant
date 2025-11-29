# Combine all individual assay figures into a grid and save as high-res PNG
if len(figs) == 8:
    # 4 rows × 2 columns portrait layout
    combined = make_subplots(
        rows=4, cols=2,
        subplot_titles=[f.layout.title.text for f in figs],
        vertical_spacing=0.07,
        horizontal_spacing=0.05
    )
    for idx, f in enumerate(figs):
        row = idx // 2 + 1
        col = idx % 2 + 1
        for trace in f.data:
            # Only show legend for histogram traces of the first assay
            if idx == 0 and trace.type == "histogram":
                trace.showlegend = True
            else:
                trace.showlegend = False
            combined.add_trace(trace, row=row, col=col)

    combined.update_layout(
        height=3508,  # A4 portrait height at 300 DPI
        width=2480,   # A4 portrait width at 300 DPI
        showlegend=True,
        template='plotly_white',
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(t=80, l=40, r=40, b=40),
        legend=dict(font=dict(size=40)), 
    )
    combined.update_traces(marker=dict(size=25), selector=dict(type="histogram"))
    combined.update_annotations(font_size=45)

    # Increase axis tick label sizes for readability
    combined.update_xaxes(
        title_text=r"$\Huge\cos\theta$",
        title_font=dict(size=50),
        tickfont=dict(size=26)
    )
    combined.update_yaxes(
        title_text="Frequency",
        title_font=dict(size=38),
        tickfont=dict(size=26)
    )
    # Enforce uniform y-axis across all subplots
    combined.update_yaxes(range=[0, 14])

    for trace in combined.data:
        trace.opacity = 0.7
    # Lightly increase KDE line widths for better visibility
    for trace in combined.data:
        if getattr(trace, "mode", "") == "lines":
            trace.line.width = 6

    # Export combined image
    output_all = base_dir / "all_assays_cossim_dist_highres.png"
    pio.write_image(
        combined,
        str(output_all),
        format="png",
        width=2480,
        height=3508,
        scale=1,
        engine="kaleido"
    )
    print(f"Saved combined image to {output_all}")
    combined.show()
