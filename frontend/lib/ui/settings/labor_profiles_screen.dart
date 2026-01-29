import 'package:flutter/material.dart';
import '../../models/agent_models.dart';
import '../../services/labor_profile_service.dart';
import '../../utils/security_utils.dart';
import '../theme/app_theme.dart';
import '../components/impact_toast.dart';
import 'widgets/labor_profile_form.dart';
import 'widgets/clone_profile_dialog.dart';

class LaborProfilesScreen extends StatefulWidget {
  const LaborProfilesScreen({super.key});

  @override
  State<LaborProfilesScreen> createState() => _LaborProfilesScreenState();
}

class _LaborProfilesScreenState extends State<LaborProfilesScreen> {
  final LaborProfileService _service = LaborProfileService();
  List<LaborProfile> _profiles = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadProfiles();
  }

  Future<void> _loadProfiles() async {
    setState(() => _isLoading = true);
    try {
      final profiles = await _service.getProfiles(SecurityUtils.activeEnvironment);
      setState(() {
        _profiles = profiles;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ImpactToast.show(context, "Errore nel caricamento dei profili: $e", isError: true);
      }
    }
  }

  void _showProfileForm({LaborProfile? profile}) {
    showDialog(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: Colors.transparent,
        child: LaborProfileForm(
          profile: profile,
          companyId: SecurityUtils.activeEnvironment,
          onSave: (savedProfile) {
            _loadProfiles();
            Navigator.pop(context);
            ImpactToast.show(context, "Profilo salvato correttamente");
          },
        ),
      ),
    );
  }

  Future<void> _deleteProfile(String id) async {
    try {
      await _service.deleteProfile(id);
      _loadProfiles();
      if (mounted) {
        ImpactToast.show(context, "Profilo eliminato");
      }
    } catch (e) {
      if (mounted) {
        ImpactToast.show(context, "Errore durante l'eliminazione: $e", isError: true);
      }
    }
  }

  void _showCloneDialog(LaborProfile profile) {
    showDialog(
      context: context,
      builder: (context) => CloneProfileDialog(
        profile: profile,
        onCloned: () {
          _loadProfiles();
          Navigator.pop(context);
          ImpactToast.show(context, "Profilo clonato con successo");
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        title: const Text("PROFILI NORMATIVI"),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _loadProfiles,
          ),
        ],
      ),
      body: Stack(
        children: [
          // Theme Background
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [AppTheme.background, const Color(0xFF1E1B4B)],
              ),
            ),
          ),
          SafeArea(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: AppTheme.aiGlow))
                : Padding(
                    padding: const EdgeInsets.all(24.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              "Gestione Paletti Contrattuali",
                              style: Theme.of(context).textTheme.headlineMedium,
                            ),
                            ElevatedButton.icon(
                              onPressed: () => _showProfileForm(),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: AppTheme.aiGlow,
                                foregroundColor: Colors.white,
                                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                              ),
                              icon: const Icon(Icons.add_rounded),
                              label: const Text("NUOVO PROFILO"),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          "Definisci i limiti di ore e riposo per diverse tipologie di contratto.",
                          style: TextStyle(color: AppTheme.textSecondary),
                        ),
                        const SizedBox(height: 32),
                        Expanded(
                          child: _profiles.isEmpty
                              ? _buildEmptyState()
                              : GridView.builder(
                                  gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                                    maxCrossAxisExtent: 400,
                                    mainAxisSpacing: 20,
                                    crossAxisSpacing: 20,
                                    childAspectRatio: 1.6,
                                  ),
                                  itemCount: _profiles.length,
                                  itemBuilder: (context, index) {
                                    final profile = _profiles[index];
                                    return _buildProfileCard(profile);
                                  },
                                ),
                        ),
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.gavel_rounded, size: 64, color: AppTheme.textSecondary.withOpacity(0.2)),
          const SizedBox(height: 16),
          Text(
            "Nessun profilo configurato",
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 18),
          ),
          const SizedBox(height: 24),
          TextButton(
            onPressed: () => _showProfileForm(),
            child: const Text("CREA IL PRIMO PROFILO", style: TextStyle(color: AppTheme.aiGlow)),
          ),
        ],
      ),
    );
  }

  Widget _buildProfileCard(LaborProfile profile) {
    return Container(
      decoration: AppTheme.glassDecoration(),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  profile.name,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (profile.isDefault)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.blueAccent.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.blueAccent.withOpacity(0.5)),
                  ),
                  child: const Text(
                    "DEFAULT",
                    style: TextStyle(color: Colors.blueAccent, fontSize: 10, fontWeight: FontWeight.bold),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),
          _buildInfoRow(Icons.timer_outlined, "Max Settimanali: ${profile.maxWeeklyHours}h"),
          _buildInfoRow(Icons.today_outlined, "Max Giornalieri: ${profile.maxDailyHours}h"),
          _buildInfoRow(Icons.hotel_outlined, "Min Riposo: ${profile.minRestHours}h"),
          const Spacer(),
          const Divider(color: Colors.white10),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              IconButton(
                icon: const Icon(Icons.copy_rounded, color: Colors.blueAccent, size: 20),
                tooltip: "Clona profilo",
                onPressed: () => _showCloneDialog(profile),
              ),
              IconButton(
                icon: const Icon(Icons.edit_rounded, color: AppTheme.textSecondary, size: 20),
                tooltip: "Modifica",
                onPressed: () => _showProfileForm(profile: profile),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline_rounded, color: Colors.redAccent, size: 20),
                tooltip: "Elimina",
                onPressed: () => _deleteProfile(profile.id),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInfoRow(IconData icon, String label) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6.0),
      child: Row(
        children: [
          Icon(icon, size: 14, color: AppTheme.textSecondary),
          const SizedBox(width: 8),
          Text(label, style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
        ],
      ),
    );
  }
}
