/// Data models matching backend Pydantic schemas

class TenderSource {
  final String id;
  final String name;
  final String shortName;
  final String color;
  final bool isActive;
  final int tenderCount;
  final String? lastParsedAt;

  TenderSource({
    required this.id,
    required this.name,
    required this.shortName,
    required this.color,
    this.isActive = true,
    this.tenderCount = 0,
    this.lastParsedAt,
  });

  factory TenderSource.fromJson(Map<String, dynamic> json) => TenderSource(
    id: json['id'] ?? '',
    name: json['name'] ?? '',
    shortName: json['short_name'] ?? '',
    color: json['color'] ?? '#666666',
    isActive: json['is_active'] ?? true,
    tenderCount: json['tender_count'] ?? 0,
    lastParsedAt: json['last_parsed_at'],
  );
}


class Tender {
  final String id;
  final String sourceId;
  final String sourceNumber;
  final String? sourceUrl;
  final String title;
  final String? description;
  final String lawType;
  final String? purchaseType;
  final List<String> okvedCodes;
  final double? nmck;
  final String? customerName;
  final String? customerInn;
  final String? winnerName;
  final String? region;
  final String? publishDate;
  final String? deadline;
  final String status;
  // Enriched
  final String? sourceName;
  final String? sourceColor;

  Tender({
    required this.id,
    required this.sourceId,
    required this.sourceNumber,
    this.sourceUrl,
    required this.title,
    this.description,
    required this.lawType,
    this.purchaseType,
    this.okvedCodes = const [],
    this.nmck,
    this.customerName,
    this.customerInn,
    this.winnerName,
    this.region,
    this.publishDate,
    this.deadline,
    this.status = 'active',
    this.sourceName,
    this.sourceColor,
  });

  factory Tender.fromJson(Map<String, dynamic> json) => Tender(
    id: json['id'] ?? '',
    sourceId: json['source_id'] ?? '',
    sourceNumber: json['source_number'] ?? '',
    sourceUrl: json['source_url'],
    title: json['title'] ?? '',
    description: json['description'],
    lawType: json['law_type'] ?? '',
    purchaseType: json['purchase_type'],
    okvedCodes: List<String>.from(json['okved_codes'] ?? []),
    nmck: (json['nmck'] as num?)?.toDouble(),
    customerName: json['customer_name'],
    customerInn: json['customer_inn'],
    winnerName: json['winner_name'],
    region: json['region'],
    publishDate: json['publish_date'],
    deadline: json['deadline'],
    status: json['status'] ?? 'active',
    sourceName: json['source_name'],
    sourceColor: json['source_color'],
  );

  String get formattedPrice {
    if (nmck == null) return 'Не указана';
    if (nmck! >= 1e9) return '${(nmck! / 1e9).toStringAsFixed(1)} млрд ₽';
    if (nmck! >= 1e6) return '${(nmck! / 1e6).toStringAsFixed(0)} млн ₽';
    if (nmck! >= 1e3) return '${(nmck! / 1e3).toStringAsFixed(0)} тыс. ₽';
    return '${nmck!.toStringAsFixed(0)} ₽';
  }
}


class TenderListResponse {
  final int total;
  final int page;
  final int perPage;
  final List<Tender> items;
  final Map<String, int> sourceCounts;

  TenderListResponse({
    required this.total,
    required this.page,
    required this.perPage,
    required this.items,
    this.sourceCounts = const {},
  });

  factory TenderListResponse.fromJson(Map<String, dynamic> json) => TenderListResponse(
    total: json['total'] ?? 0,
    page: json['page'] ?? 1,
    perPage: json['per_page'] ?? 20,
    items: (json['items'] as List? ?? []).map((e) => Tender.fromJson(e)).toList(),
    sourceCounts: Map<String, int>.from(json['source_counts'] ?? {}),
  );
}


class Company {
  final String id;
  final String inn;
  final String? ogrn;
  final String fullName;
  final String? shortName;
  final String? region;
  final String? directorName;
  final String? primaryOkved;
  final String? companyType;
  final String status;
  final int tenderWinsCount;
  final double? tenderWinsSum;
  final int arbitrationCount;
  final bool hasSro;
  final bool isVerified;
  // Detail fields
  final List<CompanyOkved>? okveds;
  final List<Contact>? contacts;
  final List<SroPermit>? sroPermits;
  final List<Financial>? financials;

  Company({
    required this.id,
    required this.inn,
    this.ogrn,
    required this.fullName,
    this.shortName,
    this.region,
    this.directorName,
    this.primaryOkved,
    this.companyType,
    this.status = 'active',
    this.tenderWinsCount = 0,
    this.tenderWinsSum,
    this.arbitrationCount = 0,
    this.hasSro = false,
    this.isVerified = false,
    this.okveds,
    this.contacts,
    this.sroPermits,
    this.financials,
  });

  factory Company.fromJson(Map<String, dynamic> json) => Company(
    id: json['id'] ?? '',
    inn: json['inn'] ?? '',
    ogrn: json['ogrn'],
    fullName: json['full_name'] ?? '',
    shortName: json['short_name'],
    region: json['region'],
    directorName: json['director_name'],
    primaryOkved: json['primary_okved'],
    companyType: json['company_type'],
    status: json['status'] ?? 'active',
    tenderWinsCount: json['tender_wins_count'] ?? 0,
    tenderWinsSum: (json['tender_wins_sum'] as num?)?.toDouble(),
    arbitrationCount: json['arbitration_count'] ?? 0,
    hasSro: json['has_sro'] ?? false,
    isVerified: json['is_verified'] ?? false,
    okveds: (json['okveds'] as List?)?.map((e) => CompanyOkved.fromJson(e)).toList(),
    contacts: (json['contacts'] as List?)?.map((e) => Contact.fromJson(e)).toList(),
    sroPermits: (json['sro_permits'] as List?)?.map((e) => SroPermit.fromJson(e)).toList(),
    financials: (json['financials'] as List?)?.map((e) => Financial.fromJson(e)).toList(),
  );
}

class CompanyOkved {
  final String okvedCode;
  final bool isPrimary;
  CompanyOkved({required this.okvedCode, this.isPrimary = false});
  factory CompanyOkved.fromJson(Map<String, dynamic> json) => CompanyOkved(
    okvedCode: json['okved_code'] ?? '', isPrimary: json['is_primary'] ?? false,
  );
}

class Contact {
  final String contactType;
  final String value;
  final bool isPrimary;
  Contact({required this.contactType, required this.value, this.isPrimary = false});
  factory Contact.fromJson(Map<String, dynamic> json) => Contact(
    contactType: json['contact_type'] ?? '', value: json['value'] ?? '', isPrimary: json['is_primary'] ?? false,
  );
}

class SroPermit {
  final String sroName;
  final String? permitNumber;
  final String status;
  SroPermit({required this.sroName, this.permitNumber, this.status = 'active'});
  factory SroPermit.fromJson(Map<String, dynamic> json) => SroPermit(
    sroName: json['sro_name'] ?? '', permitNumber: json['permit_number'], status: json['status'] ?? 'active',
  );
}

class Financial {
  final int year;
  final double? revenue;
  final double? profit;
  final int? employees;
  Financial({required this.year, this.revenue, this.profit, this.employees});
  factory Financial.fromJson(Map<String, dynamic> json) => Financial(
    year: json['year'] ?? 0, revenue: (json['revenue'] as num?)?.toDouble(),
    profit: (json['profit'] as num?)?.toDouble(), employees: json['employees'],
  );

  String get formattedRevenue {
    if (revenue == null) return '—';
    if (revenue! >= 1e9) return '${(revenue! / 1e9).toStringAsFixed(1)} млрд';
    if (revenue! >= 1e6) return '${(revenue! / 1e6).toStringAsFixed(0)} млн';
    return '${(revenue! / 1e3).toStringAsFixed(0)} тыс.';
  }
}


class SubcontractRequest {
  final String id;
  final String title;
  final String? description;
  final String? category;
  final String? budgetText;
  final String? region;
  final String? companyName;
  final String status;
  final String? publishDate;
  final String? sourceUrl;

  SubcontractRequest({
    required this.id, required this.title, this.description, this.category,
    this.budgetText, this.region, this.companyName, this.status = 'active',
    this.publishDate, this.sourceUrl,
  });

  factory SubcontractRequest.fromJson(Map<String, dynamic> json) => SubcontractRequest(
    id: json['id'] ?? '', title: json['title'] ?? '', description: json['description'],
    category: json['category'], budgetText: json['budget_text'], region: json['region'],
    companyName: json['company_name'], status: json['status'] ?? 'active',
    publishDate: json['publish_date'], sourceUrl: json['source_url'],
  );
}
