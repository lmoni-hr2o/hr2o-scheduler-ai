import 'package:flutter/material.dart';
import '../../../models/agent_models.dart';
import '../../../services/labor_profile_service.dart';
import '../../theme/app_theme.dart';

class LaborProfileForm extends StatefulWidget {
  final LaborProfile? profile;
  final String companyId;
  final Function(LaborProfile) onSave;

  const LaborProfileForm({
    super.key,
    this.profile,
    required this.companyId,
    required this.onSave,
  });

  @override
  State<LaborProfileForm> createState() => _LaborProfileFormState();
}

class _LaborProfileFormState extends State<LaborProfileForm> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _nameController;
  late TextEditingController _maxWeeklyController;
  late TextEditingController _maxDailyController;
  late TextEditingController _maxConsecutiveController;
  late TextEditingController _minRestController;
  bool _isDefault = false;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.profile?.name ?? "");
    _maxWeeklyController = TextEditingController(text: widget.profile?.maxWeeklyHours.toString() ?? "40.0");
    _maxDailyController = TextEditingController(text: widget.profile?.maxDailyHours.toString() ?? "8.0");
    _maxConsecutiveController = TextEditingController(text: widget.profile?.maxConsecutiveDays.toString() ?? "6");
    _minRestController = TextEditingController(text: widget.profile?.minRestHours.toString() ?? "11.0");
    _isDefault = widget.profile?.isDefault ?? false;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _maxWeeklyController.dispose();
    _maxDailyController.dispose();
    _maxConsecutiveController.dispose();
    _minRestController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isSaving = true);
    
    final newProfile = LaborProfile(
      id: widget.profile?.id ?? "",
      name: _nameController.text,
      companyId: widget.companyId,
      maxWeeklyHours: double.parse(_maxWeeklyController.text),
      maxDailyHours: double.parse(_maxDailyController.text),
      maxConsecutiveDays: int.parse(_maxConsecutiveController.text),
      minRestHours: double.parse(_minRestController.text),
      isDefault: _isDefault,
    );

    try {
      final saved = await LaborProfileService().saveProfile(newProfile);
      widget.onSave(saved);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Errore: $e"), backgroundColor: Colors.redAccent));
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 500,
      padding: const EdgeInsets.all(32),
      decoration: AppTheme.glassDecoration(opacity: 0.15),
      child: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.profile == null ? "Nuovo Profilo" : "Modifica Profilo",
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 24),
              _buildTextField(_nameController, "Nome Profilo (es. Part-Time 20h)", Icons.badge_outlined),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(child: _buildTextField(_maxWeeklyController, "Max Settimanali", Icons.timer_outlined, isNumeric: true)),
                  const SizedBox(width: 16),
                  Expanded(child: _buildTextField(_maxDailyController, "Max Giornalieri", Icons.today_outlined, isNumeric: true)),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(child: _buildTextField(_maxConsecutiveController, "Max Giorni Cons.", Icons.calendar_today_outlined, isNumeric: true)),
                  const SizedBox(width: 16),
                  Expanded(child: _buildTextField(_minRestController, "Min Riposo (ore)", Icons.hotel_outlined, isNumeric: true)),
                ],
              ),
              const SizedBox(height: 24),
              SwitchListTile(
                title: const Text("Imposta come Default", style: TextStyle(color: Colors.white, fontSize: 14)),
                subtitle: Text("I nuovi dipendenti useranno questo profilo", style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
                value: _isDefault,
                activeColor: AppTheme.aiGlow,
                onChanged: (v) => setState(() => _isDefault = v),
              ),
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
                    onPressed: _isSaving ? null : _submit,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.aiGlow,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                    ),
                    child: _isSaving 
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Text(widget.profile == null ? "CREA" : "SALVA"),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTextField(TextEditingController controller, String label, IconData icon, {bool isNumeric = false}) {
    return TextFormField(
      controller: controller,
      keyboardType: isNumeric ? const TextInputType.numberWithOptions(decimal: true) : TextInputType.text,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: TextStyle(color: AppTheme.textSecondary),
        prefixIcon: Icon(icon, color: AppTheme.aiGlow, size: 20),
        filled: true,
        fillColor: Colors.white.withOpacity(0.05),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.aiGlow)),
      ),
      validator: (v) {
        if (v == null || v.isEmpty) return "Campo obbligatorio";
        if (isNumeric && double.tryParse(v) == null) return "Inserire un numero";
        return null;
      },
    );
  }
}
