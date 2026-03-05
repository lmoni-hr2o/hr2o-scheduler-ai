import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../../models/agent_models.dart';

class ShiftCard extends StatelessWidget {
  final Map<String, dynamic> shift;
  final double? affinity;
  final double? absenceRisk; // NEW
  final String? historicalTime;
  final List<Activity> activities;
  final Map<String, String>? activityNameMap;

  const ShiftCard({
    super.key, 
    required this.shift,
    this.affinity,
    this.absenceRisk,
    this.historicalTime,
    required this.activities,
    this.activityNameMap,
  });

  @override
  Widget build(BuildContext context) {
    final startTime = shift['start_time'];
    final endTime = shift['end_time'];
    final bool isGrouped = shift['is_grouped'] == true;
    final List<dynamic> subShifts = shift['sub_shifts'] ?? [shift];
    
    // Total label for the presence
    final presenceLabel = "$startTime - $endTime";

    return Draggable<Map<String, dynamic>>(
      data: shift,
      feedback: Material(
        color: Colors.transparent,
        child: _buildCardContent(context, presenceLabel, subShifts, scaling: 1.1),
      ),
      childWhenDragging: Opacity(
        opacity: 0.3,
        child: _buildCardContent(context, presenceLabel, subShifts),
      ),
      child: InkWell(
        onTap: () => _showShiftDetails(context, subShifts),
        borderRadius: BorderRadius.circular(8),
        child: _buildCardContent(context, presenceLabel, subShifts),
      ),
    );
  }

  void _showShiftDetails(BuildContext context, List<dynamic> subs) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF1E1B4B),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24), side: BorderSide(color: AppTheme.aiGlow.withOpacity(0.3))),
        title: Row(
          children: [
            const Icon(Icons.calendar_month_rounded, color: AppTheme.aiGlow),
            const SizedBox(width: 12),
            const Text("Dettagli Giornata", style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 18)),
          ],
        ),
        content: SizedBox(
          width: 400,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: subs.map((s) {
              String? actName;
              final String? aid = s['activity_id']?.toString();
              if (aid != null) {
                actName = activityNameMap?[aid] ?? activities.where((a) => a.id.toString() == aid).firstOrNull?.name;
              }
              return Container(
                margin: const EdgeInsets.only(bottom: 12),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: Colors.black26, borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.white10)),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(aid != null ? Icons.work_rounded : Icons.access_time_filled_rounded, color: Colors.blueAccent, size: 16),
                        const SizedBox(width: 8),
                        Text("${s['start_time']} - ${s['end_time']}", style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.bold, fontSize: 12)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(actName ?? "Lavoro Generico (Non Collegato)", style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 13)),
                  ],
                ),
              );
            }).toList(),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text("CHIUDI", style: TextStyle(color: Colors.white60))),
        ],
      ),
    );
  }

  Widget _buildCardContent(BuildContext context, String presenceLabel, List<dynamic> subs, {double scaling = 1.0}) {
    final double score = affinity ?? 0.0;
    
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      decoration: BoxDecoration(
        color: AppTheme.primary.withOpacity(0.15),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: score > 0.8 ? AppTheme.aiGlow.withOpacity(0.5) : AppTheme.primary.withOpacity(0.3), width: 1),
        boxShadow: score > 0.9 ? [BoxShadow(color: AppTheme.aiGlow.withOpacity(0.1), blurRadius: 4, spreadRadius: 1)] : null,
      ),
      child: Transform.scale(
        scale: scaling,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Presence header
            Row(
              children: [
                const Icon(Icons.timer_outlined, size: 10, color: AppTheme.aiGlow),
                const SizedBox(width: 4),
                Text(presenceLabel, style: const TextStyle(color: AppTheme.textPrimary, fontSize: 10, fontWeight: FontWeight.w900, decoration: TextDecoration.none)),
              ],
            ),
            const SizedBox(height: 4),
            // Sub-Shift List (Commesse)
            ...subs.take(2).map((s) {
              final String? aid = s['activity_id']?.toString();
              String name = s['activity_name']?.toString() ?? 
                (aid != null 
                  ? (activityNameMap?[aid] ?? activities.where((a) => a.id.toString() == aid).firstOrNull?.name ?? "Commessa")
                  : "Generico");
              
              bool isGeneric = name.toLowerCase().contains("generico") || name.toLowerCase().contains("normale") || aid == null;
              
              return Padding(
                padding: const EdgeInsets.only(bottom: 2),
                child: Row(
                  children: [
                    Icon(isGeneric ? Icons.circle_outlined : Icons.circle, size: 6, color: isGeneric ? Colors.white24 : Colors.blueAccent),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        name,
                        style: TextStyle(color: isGeneric ? Colors.white38 : Colors.white.withOpacity(0.9), fontSize: 8, fontWeight: FontWeight.w500, decoration: TextDecoration.none, overflow: TextOverflow.ellipsis),
                      ),
                    ),
                  ],
                ),
              );
            }),
            if (subs.length > 2)
              Text("+${subs.length - 2} altre", style: const TextStyle(color: Colors.white24, fontSize: 7, decoration: TextDecoration.none)),
            
            // AI Affinity line
            if (affinity != null) ...[
              const SizedBox(height: 4),
              Container(
                height: 2,
                width: double.infinity,
                decoration: BoxDecoration(color: Colors.black12, borderRadius: BorderRadius.circular(1)),
                child: FractionallySizedBox(
                  alignment: Alignment.centerLeft,
                  widthFactor: score.clamp(0.0, 1.0),
                  child: Container(decoration: BoxDecoration(borderRadius: BorderRadius.circular(1), gradient: LinearGradient(colors: [Colors.orange, AppTheme.aiGlow]))),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
