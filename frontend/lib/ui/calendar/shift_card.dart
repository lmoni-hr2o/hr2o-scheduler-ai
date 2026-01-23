import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../../models/agent_models.dart';

class ShiftCard extends StatelessWidget {
  final Map<String, dynamic> shift;
  final double? affinity;
  final String? historicalTime;
  final List<Activity> activities;

  const ShiftCard({
    super.key, 
    required this.shift,
    this.affinity,
    this.historicalTime,
    required this.activities,
  });

  @override
  Widget build(BuildContext context) {
    final startTime = shift['start_time'];
    final endTime = shift['end_time'];
    
    // Look up activity name
    String? activityName;
    if (shift['activity_id'] != null) {
      final act = activities.where((a) => a.id == shift['activity_id']).firstOrNull;
      activityName = act?.name;
    }

    final displayLabel = activityName ?? 
        ((startTime != null && endTime != null) 
            ? "$startTime - $endTime" 
            : (shift['label'] ?? "Turno"));

    return Draggable<Map<String, dynamic>>(
      data: shift,
      feedback: Material(
        color: Colors.transparent,
        child: _buildCardContent(context, displayLabel, scaling: 1.1),
      ),
      childWhenDragging: Opacity(
        opacity: 0.3,
        child: _buildCardContent(context, displayLabel),
      ),
      child: InkWell(
        onTap: () => _showShiftDetails(context, activityName),
        borderRadius: BorderRadius.circular(8),
        child: _buildCardContent(context, displayLabel),
      ),
    );
  }

  void _showShiftDetails(BuildContext context, String? activityName) {
    final score = affinity ?? 0.0;
    final project = shift['project'] as Map<String, dynamic>?;
    final customer = project != null ? project['customer'] as Map<String, dynamic>? : null;

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF1E1B4B),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: BorderSide(color: AppTheme.aiGlow.withOpacity(0.3)),
        ),
        title: Row(
          children: [
            Icon(
              shift['activity_id'] != null ? Icons.work_rounded : Icons.access_time_filled_rounded,
              color: AppTheme.aiGlow,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                shift['activity_id'] != null ? "Dettagli Commessa" : "Dettagli Turno",
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 18),
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (activityName != null) ...[
              _buildDetailRow("Attività", activityName, Icons.assignment_rounded),
              const SizedBox(height: 12),
            ],
            if (project != null) ...[
              _buildDetailRow("Progetto", project['name'] ?? "N/A", Icons.folder_special_rounded),
              const SizedBox(height: 12),
            ],
            if (customer != null) ...[
              _buildDetailRow("Cliente", customer['name'] ?? "N/A", Icons.person_pin_rounded),
              const SizedBox(height: 12),
            ],
            _buildDetailRow("Orario", "${shift['start_time']} - ${shift['end_time']}", Icons.schedule_rounded),
            const SizedBox(height: 24),
            
            // Brain Satisfaction Bar
            const Text(
              "NEURAL AFFINITY",
              style: TextStyle(color: Colors.white54, fontSize: 10, fontWeight: FontWeight.w900, letterSpacing: 1.5),
            ),
            const SizedBox(height: 12),
            Container(
              height: 45,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              decoration: BoxDecoration(
                color: Colors.black26,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white10),
              ),
              child: Row(
                children: [
                  const Icon(Icons.psychology_rounded, color: AppTheme.aiGlow, size: 20),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              "${(score * 100).toInt()}% Confidence",
                              style: TextStyle(
                                color: score > 0.8 ? AppTheme.aiGlow : Colors.orangeAccent,
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Text(
                              score > 0.8 ? "OTTIMO" : "BUONO",
                              style: TextStyle(color: Colors.white38, fontSize: 10, fontWeight: FontWeight.w900),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        LinearProgressIndicator(
                          value: score,
                          backgroundColor: Colors.white12,
                          color: score > 0.8 ? AppTheme.aiGlow : Colors.orangeAccent,
                          minHeight: 4,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            
            // AI Reasoning Section
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.aiGlow.withOpacity(0.05),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.aiGlow.withOpacity(0.1)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.auto_awesome, color: AppTheme.aiGlow, size: 16),
                      const SizedBox(width: 8),
                      const Text(
                        "AI REASONING (MIA)",
                        style: TextStyle(color: AppTheme.aiGlow, fontSize: 9, fontWeight: FontWeight.w900, letterSpacing: 1),
                      ),
                      const Spacer(),
                      Tooltip(
                        message: "MIA è pre-addestrata su migliaia di turni globali. Impara orari tipici, tempi di percorrezza, e come età o distanza influenzano la stanchezza.",
                        child: Icon(Icons.info_outline_rounded, color: AppTheme.aiGlow.withOpacity(0.5), size: 14),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    "Questo turno è stato valutato incrociando lo storico globale e parametri locali:",
                    style: TextStyle(color: Colors.white60, fontSize: 11),
                  ),
                  const SizedBox(height: 8),
                  _buildMiniTag("Prossimità alla sede", Icons.location_on_outlined),
                  _buildMiniTag("Anzianità di servizio", Icons.history_edu_rounded),
                  _buildMiniTag("Bilanciamento ore settimanali", Icons.balance_rounded),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("CHIUDI", style: TextStyle(color: Colors.white60, fontWeight: FontWeight.w900)),
          ),
        ],
      ),
    );
  }

  Widget _buildMiniTag(String text, IconData icon) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          Icon(icon, size: 10, color: AppTheme.aiGlow.withOpacity(0.7)),
          const SizedBox(width: 8),
          Text(text, style: const TextStyle(color: Colors.white38, fontSize: 10, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _buildDetailRow(String label, String value, IconData icon) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(color: Colors.white.withOpacity(0.05), borderRadius: BorderRadius.circular(8)),
          child: Icon(icon, color: Colors.blueAccent, size: 16),
        ),
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label.toUpperCase(), style: const TextStyle(color: Colors.white38, fontSize: 9, fontWeight: FontWeight.w900, letterSpacing: 1)),
            Text(value, style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
          ],
        ),
      ],
    );
  }

  Widget _buildCardContent(BuildContext context, String text, {double scaling = 1.0}) {
    final double score = affinity ?? 0.0;
    final bool isHighConfidence = score > 0.8;
    final bool isLowConfidence = score < 0.5;
    
    final Color borderColor = isHighConfidence 
        ? AppTheme.aiGlow 
        : (isLowConfidence ? Colors.orangeAccent : AppTheme.primary.withOpacity(0.5));
    
    final double borderWidth = isHighConfidence ? 1.5 : 0.8;

    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(minHeight: 40),
      margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: AppTheme.primary.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: borderColor,
          width: borderWidth,
        ),
      ),
      child: Transform.scale(
        scale: scaling,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Row(
              children: [
                Icon(Icons.access_time_filled_rounded, size: 12, color: AppTheme.textSecondary),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    text,
                    style: const TextStyle(
                      color: AppTheme.textPrimary,
                      fontSize: 11, // Increased size
                      fontWeight: FontWeight.w800, // Thicker
                      decoration: TextDecoration.none,
                    ),
                  ),
                ),
              ],
            ),
            if (historicalTime != null && historicalTime != text) ...[
              const SizedBox(height: 2),
              Row(
                children: [
                  const Icon(Icons.history, size: 10, color: Colors.amber),
                  const SizedBox(width: 4),
                  Text(
                    "Prev: $historicalTime",
                    style: TextStyle(
                      color: Colors.amber.withOpacity(0.8),
                      fontSize: 8,
                      fontWeight: FontWeight.w600,
                      decoration: TextDecoration.none,
                    ),
                  ),
                ],
              ),
            ],
            if (affinity != null) ...[
              const SizedBox(height: 4),
              Container(
                height: 3,
                width: double.infinity,
                decoration: BoxDecoration(
                  color: Colors.black12,
                  borderRadius: BorderRadius.circular(1.5),
                ),
                child: FractionallySizedBox(
                  alignment: Alignment.centerLeft,
                  widthFactor: score.clamp(0.0, 1.0),
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(1.5),
                      gradient: LinearGradient(
                        colors: [
                          Colors.redAccent.withOpacity(0.8),
                          Colors.orangeAccent,
                          AppTheme.aiGlow,
                        ],
                      ),
                    ),
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
