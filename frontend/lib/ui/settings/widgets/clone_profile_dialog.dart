import 'package:flutter/material.dart';
import '../../../models/agent_models.dart';
import '../../../models/company_model.dart';
import '../../../services/labor_profile_service.dart';
import '../../../repositories/schedule_repository.dart';
import '../../theme/app_theme.dart';

class CloneProfileDialog extends StatefulWidget {
  final LaborProfile profile;
  final VoidCallback onCloned;

  const CloneProfileDialog({
    super.key,
    required this.profile,
    required this.onCloned,
  });

  @override
  State<CloneProfileDialog> createState() => _CloneProfileDialogState();
}

class _CloneProfileDialogState extends State<CloneProfileDialog> {
  final LaborProfileService _profileService = LaborProfileService();
  final ScheduleRepository _scheduleRepository = ScheduleRepository();
  List<Company> _companies = [];
  String? _selectedCompanyId;
  bool _isLoading = true;
  bool _isCloning = false;

  @override
  void initState() {
    super.initState();
    _loadCompanies();
  }

  Future<void> _loadCompanies() async {
    try {
      final companies = await _scheduleRepository.getCompanies();
      setState(() {
        _companies = companies.where((c) => c.id != widget.profile.companyId).toList();
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Errore caricamento aziende: $e")));
      }
    }
  }

  Future<void> _clone() async {
    if (_selectedCompanyId == null) return;
    setState(() => _isCloning = true);
    try {
      await _profileService.cloneProfile(widget.profile.id, _selectedCompanyId!);
      widget.onCloned();
    } catch (e) {
      if (mounted) {
        setState(() => _isCloning = false);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Errore durante la clonazione: $e")));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: Colors.transparent,
      child: Container(
        width: 400,
        padding: const EdgeInsets.all(32),
        decoration: AppTheme.glassDecoration(opacity: 0.15),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("Clona Profilo", style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 8),
            Text(
              "Copia '${widget.profile.name}' in un'altra azienda.",
              style: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
            ),
            const SizedBox(height: 24),
            if (_isLoading)
              const Center(child: CircularProgressIndicator(color: AppTheme.aiGlow))
            else if (_companies.isEmpty)
              Text("Nessuna altra azienda disponibile.", style: TextStyle(color: AppTheme.textSecondary))
            else
              _buildCompanyDropdown(),
            const SizedBox(height: 32),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text("ANNULLA", style: TextStyle(color: AppTheme.textSecondary)),
                ),
                const SizedBox(width: 16),
                ElevatedButton(
                  onPressed: (_isCloning || _selectedCompanyId == null) ? null : _clone,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blueAccent,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                  ),
                  child: _isCloning 
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text("CLONA"),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCompanyDropdown() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: _selectedCompanyId,
          hint: Text("Seleziona azienda di destinazione", style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
          dropdownColor: AppTheme.surface,
          isExpanded: true,
          icon: const Icon(Icons.keyboard_arrow_down_rounded, color: AppTheme.textSecondary),
          items: _companies.map((c) => DropdownMenuItem(
            value: c.id,
            child: Text(c.name, style: const TextStyle(color: Colors.white, fontSize: 14)),
          )).toList(),
          onChanged: (v) => setState(() => _selectedCompanyId = v),
        ),
      ),
    );
  }
}
