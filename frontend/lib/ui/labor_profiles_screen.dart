import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../repositories/schedule_repository.dart';
import '../models/agent_models.dart';
import 'theme/app_theme.dart';

class LaborProfilesScreen extends StatefulWidget {
  const LaborProfilesScreen({Key? key}) : super(key: key);

  @override
  _LaborProfilesScreenState createState() => _LaborProfilesScreenState();
}

class _LaborProfilesScreenState extends State<LaborProfilesScreen> {
  List<LaborProfile> _profiles = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadProfiles();
  }

  Future<void> _loadProfiles() async {
    try {
      final repo = Provider.of<ScheduleRepository>(context, listen: false);
      final profiles = await repo.getLaborProfiles();
      setState(() {
        _profiles = profiles;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Error loading profiles: $e")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: Text("Profili Lavorativi"),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: _isLoading
          ? Center(child: CircularProgressIndicator(color: AppTheme.primary))
          : _profiles.isEmpty
              ? _buildEmptyState()
              : ListView.builder(
                  padding: EdgeInsets.all(16),
                  itemCount: _profiles.length,
                  itemBuilder: (context, index) {
                    final profile = _profiles[index];
                    return _buildProfileCard(profile);
                  },
                ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.assignment_ind_outlined, size: 64, color: Colors.grey),
          SizedBox(height: 16),
          Text(
            "Nessun profilo trovato",
            style: TextStyle(color: Colors.white, fontSize: 18),
          ),
          SizedBox(height: 8),
          Text(
            "Esegui una sincronizzazione per generare i profili.",
            style: TextStyle(color: Colors.grey),
          ),
        ],
      ),
    );
  }

  Widget _buildProfileCard(LaborProfile profile) {
    return Container(
      margin: EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white10),
      ),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: AppTheme.primary.withOpacity(0.2),
          child: Text(
            "${profile.maxWeeklyHours.toInt()}h",
            style: TextStyle(color: AppTheme.primary, fontWeight: FontWeight.bold, fontSize: 12),
          ),
        ),
        title: Text(
          profile.name,
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        subtitle: Text(
          "Max ${profile.maxDailyHours}h/giorno • Riposo ${profile.minRestHours}h",
          style: TextStyle(color: Colors.grey),
        ),
        trailing: Icon(Icons.chevron_right, color: Colors.grey),
      ),
    );
  }
}
