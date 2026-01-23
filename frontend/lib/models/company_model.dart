class Company {
  final String id;
  final String code;
  final String name;
  final String? address;
  final String? city;
  final String? region;
  final String? postalcode;
  final String? phone;
  final String? mail;
  final String? VATNumber;
  final String? fiscaleCode;
  final String? note;

  Company({
    required this.id,
    required this.code,
    required this.name,
    this.address,
    this.city,
    this.region,
    this.postalcode,
    this.phone,
    this.mail,
    this.VATNumber,
    this.fiscaleCode,
    this.note,
  });

  factory Company.fromJson(Map<String, dynamic> json) {
    return Company(
      id: json['id']?.toString() ?? '',
      code: json['code'] as String? ?? '',
      name: json['name'] as String? ?? 'Unknown',
      address: json['address'] as String?,
      city: json['city'] as String?,
      region: json['region'] as String?,
      postalcode: json['postalcode'] as String?,
      phone: json['phone'] as String?,
      mail: json['mail'] as String?,
      VATNumber: json['VATNumber'] as String?,
      fiscaleCode: json['fiscaleCode'] as String?,
      note: json['note'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'code': code,
      'name': name,
      if (address != null) 'address': address,
      if (city != null) 'city': city,
      if (region != null) 'region': region,
      if (postalcode != null) 'postalcode': postalcode,
      if (phone != null) 'phone': phone,
      if (mail != null) 'mail': mail,
      if (VATNumber != null) 'VATNumber': VATNumber,
      if (fiscaleCode != null) 'fiscaleCode': fiscaleCode,
      if (note != null) 'note': note,
    };
  }
}
