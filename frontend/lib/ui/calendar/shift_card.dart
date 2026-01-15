import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class ShiftCard extends StatelessWidget {
  final String label;
  final String? startTime;
  final String? endTime;
  final double? affinity;

  const ShiftCard({
    super.key, 
    required this.label,
    this.startTime,
    this.endTime,
    this.affinity,
  });

  @override
  Widget build(BuildContext context) {
    final String displayLabel = (startTime != null && endTime != null) 
        ? "$startTime - $endTime" 
        : label;

    return Draggable<String>(
      data: label,
      feedback: Material(
        color: Colors.transparent,
        child: _buildCardContent(displayLabel, scaling: 1.1),
      ),
      childWhenDragging: Opacity(
        opacity: 0.3,
        child: _buildCardContent(displayLabel),
      ),
      child: _buildCardContent(displayLabel),
    );
  }

  Widget _buildCardContent(String text, {double scaling = 1.0}) {
    final double score = affinity ?? 0.0;
    // Confidence logic: High > 0.8, Medium > 0.5, Low < 0.5
    final bool isHighConfidence = score > 0.8;
    final bool isLowConfidence = score < 0.5;
    
    final Color borderColor = isHighConfidence 
        ? AppTheme.aiGlow 
        : (isLowConfidence ? Colors.orangeAccent : AppTheme.primary.withOpacity(0.5));
    
    final double borderWidth = isHighConfidence ? 1.5 : 0.8;

    return Container(
      width: 140, // Fixed width for consistent grid look
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: AppTheme.primary.withOpacity(0.12),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: borderColor,
          width: borderWidth,
          style: isLowConfidence ? BorderStyle.solid : BorderStyle.solid, // Flutter doesn't support native dashed borders easily without CustomPainter, simulation via color for now.
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
          if (isHighConfidence)
            BoxShadow(
              color: AppTheme.aiGlow.withOpacity(0.2),
              blurRadius: 8,
              spreadRadius: 1,
            ),
        ],
      ),
      child: Transform.scale(
        scale: scaling,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: Time & Icon
            Row(
              children: [
                Icon(Icons.access_time_filled_rounded, size: 10, color: AppTheme.textSecondary),
                const SizedBox(width: 4),
                Text(
                  text,
                  style: TextStyle(
                    color: AppTheme.textPrimary,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    decoration: TextDecoration.none,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            
            // Energy Bar (Affinity)
            if (affinity != null) ...[
              Container(
                height: 4,
                width: double.infinity,
                decoration: BoxDecoration(
                  color: Colors.black12,
                  borderRadius: BorderRadius.circular(2),
                ),
                child: FractionallySizedBox(
                  alignment: Alignment.centerLeft,
                  widthFactor: score.clamp(0.0, 1.0),
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(2),
                      gradient: LinearGradient(
                        colors: [
                          Colors.redAccent.withOpacity(0.8),
                          Colors.orangeAccent,
                          AppTheme.aiGlow,
                        ],
                        stops: const [0.0, 0.5, 1.0],
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 4),
              // Confidence Label (Optional or Icon)
              Align(
                alignment: Alignment.centerRight,
                child: Text(
                  "${(score * 100).toInt()}% match",
                  style: TextStyle(
                    color: AppTheme.textSecondary.withOpacity(0.6),
                    fontSize: 7,
                    fontWeight: FontWeight.w500,
                    decoration: TextDecoration.none,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
