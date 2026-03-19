# Incident: *delta.example.org returning 4xx’s*

All times are written in UTC. use 24-hour clock and formatting via [https://en.wikipedia.org/wiki/ISO\_8601](https://en.wikipedia.org/wiki/ISO_8601)

* **Incident [Severity](https://example.net/wiki/spaces/MIR/pages/20512894/Incident+Severity+Levels)**: S2 \- High  
* **Incident Title**: delta.example.org returning 4xx’s  
* **Incident Jira Ticket**: [SREIM-17](https://example.net/browse/SREIM-17) [IIM-17](https://example.net/browse/IIM-17)   
* **Time of first Impact:** 2025-01-27T16:00:00Z UTC  
* **Time Detected**: 2025-01-27T16:03:00Z UTC  
* **Time Alerted**: 2025-01-27T16:05:00Z UTC  
* **Time Acknowledge**: 2025-01-27T16:05:00Z UTC  
* **Time Responded/Engaged**: 2025-01-27T16:03:00Z UTC  
* **Time Mitigated (Repaired)**: 2025-01-27T16:19:00Z UTC  
* **Time Resolved**: 2025-01-27T16:19:00Z UTC  
* **Video call link**:   
* **Slack channel**: \#ir-mozorg-jan27 (also \#www)  
* **Current Status**: \[Resolved\]

## Who’s on point

\<At minimum we should have these roles for any incident. Add more where needed (this saves time, biasing for speed of execution, rather than having people delete rows)\>

| Role | Name (slack handle) | Notes / supporting docs |
| :---- | :---- | :---- |
| **Incident Manager** | [Brett](mailto:brett@example.com) |  |
| **Comms** | [Paul](mailto:paul@example.com) |  |
| **Engineer(s)** | [Brett](mailto:brett@example.com) [Steve](mailto:steve@example.com) |   |
| Other (please enumerate) |  |  |

## Timeline

| YYYY MM DD @ hh:mm UTC | Person(s) | Note/comment/action |
| :---- | :---- | :---- |
| **2025 01 27 @ 15:58 UTC** | **Brett** | **Merged PR [https://example.com/company/webservices-infra/pull/3783](https://example.com/company/webservices-infra/pull/3783) this is what caused the outage** |
| **2025 01 27 @ 15:59 UTC** | **Robots** | **ArgoCD Deploys Change** |
| **2025 01 27 @ 16:03 UTC** | **Pascal** | **Notes in #www that some [www.delta.example.org](http://www.delta.example.org) pages are returning 404s ** |
| **2025 01 27 @ 16:05 UTC** | **Alex** | **Pings @brett and @steve reporting they are seeing the same** |
| **2025 01 27 @ 16:06 UTC** | **Brett** | **Puts up PR to revert a commit that rolled out at 16:00 UTC [https://example.com/company/webservices-infra/pull/3831](https://example.com/company/webservices-infra/pull/3831)** |
| **2025 01 27 @ \~ 16:08 UTC** | **Robots** | **PR is merged by Github Merge Queue and Argo autosyncs  ** |
| **2025 01 27 @ 16:10 UTC** | **Brett** | **Checked Kubernetes and can see that revert has synced and that the sync is reflected on load balancer in GCP** |
| **2025 01 27 @ 16:12 UTC** | **Brett** | **Waiting for recovery to sync out, noticed that 404 errors were being cached by cdn**  |
| **2025 01 27 @ 16:14 UTC** | **Robots** | **SRE Green team paged for [www.delta.example.org](http://www.delta.example.org) outage** |
| **2025 01 27 @ 16:16 UTC** | **Andre** | **Paged for incident reaches out and discovers we are already on it, steps down [https://mozilla.pagerduty.com/incidents/Q05HLV7DYIESQN](https://mozilla.pagerduty.com/incidents/Q05HLV7DYIESQN)**  |
| **2025 01 27 @ 16:17 UTC** | **Brett** | **Logs into cdn and issues a Purge All to stop caching 404s** |
| **2025 01 27 @ 16:19 UTC** | **Brett** | **Verified via cdn monitoring that 404s had subsided** |
| **2025 01 27 @ 16:28 UTC** | **Robots** | **All alerts and pages auto resolve** |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |

# Impact

On 2025-01-27 from 16:00 UTC \- 16:19 UTC, up to 14%[^1] of [www.delta.example.org](http://www.delta.example.org) visitor traffic received a 404 response. That response was then cached and served to subsequent users over the approximately nineteen minutes of degraded service.

The [URL path for downloading Product](https://cdn.example.net/) was working fine. So browser updates and direct links to downloads (for product, extensions, and other Mozilla tools) were working. Some additional metrics can be found [here](#additional-delta.example.org-metrics).   


# Description of the issue

As part of our full migration to cdn CDN we no longer need to issue certificates for, or have the need for an ingress, for the friendly/customer facing names such as [`www.delta.example.org`](http://www.delta.example.org) within GCP. We merged a [PR](https://example.com/company/webservices-infra/pull/3783) to fully remove the [`www.delta.example.org`](http://www.delta.example.org) ingress name and certificates from GCP at 15:58 UTC. After Argo synced this change to production 2025-01-27 15:58:57 UTC, we started to quickly thereafter receive reports and notifications that some pages were `404`ing. First notification is received via Slack at 16:03. We reverted that PR since it seemed to be the most likely culprit based on the `404` error message of backend configuration or service not found. This is an error from GCP indicating it could not find the ingress which let the responding SRE know we needed to revert the change. The change (which reverted the offending change) was auto deployed by ArgoCD and we started to see some relief. After still seeing some cached `404`s the responding SRE logged into cdn to fully purge the cache. After this change rolled out across all cdn’s edge devices we saw a full recovery from increased `404` errors.

cdn started sending traffic for [`www.delta.example.org`](http://www.delta.example.org) to a backend at [`https://prod.delta.example.org`](https://prod.delta.example.org) but with the hostname [`www.delta.example.org`](http://www.delta.example.org) which was no longer recognized on the ingress. To correct this behavior we tell cdn to send the backend hostname to the hostname instead of the default hostname being used at the CDN.

# Contributing Factors

[www.delta.example.org](http://www.delta.example.org) is served from GCP. In \~Nov 2024 we switched all traffic over from AWS CloudFront (CDN) to cdn CDN. However we had some leftover artifacts from experimenting with GCP’s CDN (more history [here](#additional-history-about-our-artifacts-in-gcp))

After migration to cdn CDN completed, we were decommissioning our GCP CDN. Deletion of the old GCP CDN config, specifically the definition of the backend service, was deployed to dev and staging, but not to production yet (this work overall was still in progress). Since [December, 16th 2024](https://example.com/company/webservices-infra/commit/dc4f1224ffedaf9a6ab0a1450009adafe574445a) Kubernetes ingress was not correctly syncing due to deletion of the CDN backend service but not the definition of the corresponding ingress object ([example change](https://example.com/company/webservices-infra/blob/511339e85734063e441f0e978583395ec5f2f546/service/k8s/service/values-dev.yaml#L68) which scopes some resources but does not remove the pointer from the ingress to the backend config). This has left us in a state in `dev` and `stage` where we aren't syncing the `ingress` . Below is the output from `kubectl describe ingress service`, and you can see a bit more info [here](#more-technical-details-about-the-cdn-changes-and-broken-sync). You can also read more about kubernetes controllers and their async behavior in the [controller documentation](https://kubernetes.io/docs/concepts/architecture/controller/).

| Events:  Type     Reason     Age                    From                     Message  \----     \------     \----                   \----                     \-------  Warning  Translate  9m15s (x428 over 43h)  loadbalancer-controller  Translation failed: invalid ingress spec: error getting BackendConfig for port "\&ServiceBackendPort{Name:,Number:8080,}" on service "service-dev/service-cdn", err: no BackendConfig for service port exists. |
| :---- |

Throughout January we had been testing removing the friendly name DNS entries (such as www-dev.elpmaxe.org and www.elpmaxe.org) in our staging and development environments. These changes looked fine in dev and staging but immediately broke in production. Due to the syncing error mentioned above the change was never actually deployed to dev or staging and our testing was invalid. There is a small change to the cdn configuration to use the overridden backend hostname which has been rolled out to dev and staging in addition to cleaning up the corresponding ingress object which prevented syncing.

# Postmortem Action Items

- [ ] \[[SE-4263](https://example.net/browse/SE-4263)\] Need to clean up `dev` and `stage` to correctly reflect the expected state in Kubernetes. This will give us a testing group to correctly test changes to `X-Forwarded-Host`   
- [ ] \[[SE-4263](https://example.net/browse/SE-4263)\] [www.delta.example.org](http://www.delta.example.org) has a fallback if the backend is considered unhealthy. cdn should have fallen back to this static page to download product rather than returning a 404\. This is configured in VCL [https://example.com/company/webservices-infra/blob/main/service/tf/modules/cdn/vcl/main.vcl.tftpl\#L1-L4](https://example.com/company/webservices-infra/blob/main/service/tf/modules/cdn/vcl/main.vcl.tftpl#L1-L4) but did not seem to trigger during this outage. After initial investigation it was determined this is due to the mismatching hostname, the service was responding to health checks correctly but returning a 404\. In the future if the service is fully down cdn will fallback to the static page.   
- [x] ~~\[[OPST-1874](https://example.net/browse/OPST-1874)\] Need alerting or monitoring around sync failures in kubernetes across our shared clusters.~~  
- [ ] \[Jira TBC\] Explore possibilities for safely simulating CDN changes.  
- [ ] \[Jira TBC\] [Dan](mailto:dan@example.com) will look at existing analytics to see impact for product downloads, and use this incident as a use case to push the need for future analytics improvements.  
- [ ] \[Jira TBC\] There is currently no assigned individual, function, or team responsible for monitoring, analyzing, or extracting website analytics, which limits our ability to assess the impact of incidents like this.  
- [ ] product pages are moving to product.com (July). In this process we will engage with an external vendor to help improve our GA4 setup for better self-serve analytics. This will also help us better understand user traffic as traffic to this domain will be product specific.

# Postmortem discussion notes

* We have an opportunity to improve change management (not unique to this incident).  
  * For example: if we’re deploying changes via ArgoCD, a part of that change would include a feedback loop about success (once the deployment lands); failure would potentially trigger alerts and rollback automatically.  
* This might be an opportunity to think about fail-open scenarios.  
* Followup on the [action item](#bookmark=id.yf64ghq1pvjv) that [Dan](mailto:dan@example.com) added.  
* Add “postmortem report” status (so we can close that when the postmortem action items have dates)  
  * State machine:  
    * Draft: Incident may still be active, or may be resolved. We’re still updating the report.  
    * Ready for Review: We’re done updating the incident report. To be reviewed with team  
    * Closed: All postmortem action items have dates assigned.

# Addendum:

### Retrospective thoughts

What went well?

* It was identified almost immediately via users and alerting  
* Revert happened quickly  
* cdn shielding mitigated the effect of stampeding requests

What could have gone better?

* Efficiency around identifying the actual user impact

### Additional history about our artifacts in GCP {#additional-history-about-our-artifacts-in-gcp}

As part of migrating [www.delta.example.org](http://www.delta.example.org) (service) from AWS to GCPv2 in early 2024, we tried using GCP CDN. This involved several iterations and implementations with guidance from Google, and some brief attempts at using their CDN in production. Eventually, we reverted back to AWS CloudFront.

Until migrating [www.delta.example.org](http://www.delta.example.org) (service) CDN to cdn we were still serving from AWS CloudFront (CDN). We did not clean up all artifacts from our GCP CDN experiments. GCP kept promising upcoming changes to fix the problems we encountered with their WAF, which would have cleared the way for us to use their CDN in production again. In \~Nov 2024, we decided we weren’t going to use GCP CDN, and we switched all traffic over from AWS CloudFront (CDN) to cdn CDN.

### More technical details about the CDN changes and broken sync {#more-technical-details-about-the-cdn-changes-and-broken-sync}

In the dev and staging environments, when looking at the ingress configuration in `dev` or `stage` in kubernetes the configuration looks correct (e.g. we don't see the corresponding friendly name like [`www-dev.elpmaxe.org`](http://www-dev.elpmaxe.org) or [`www.elpmaxe.org`](http://www.elpmaxe.org)). The configuration looks as expected but due to the sync error shown above, that configuration never actually synced to the load-balancer, so the load-balancer still has the ingress spec with the friendly name (screenshot below). The `service-cd` `backend config` still exist in production so the merge, the one that was reverted, actually worked in production but didn't work in any of our testing environments. 

| $ kubectl get backendconfigs.cloud.google.com service-cdnNAME          AGEservice-cdn   2y49d |
| :---- |


### Additional delta.example.org metrics  {#additional-delta.example.org-metrics}

No dip in metrics showing profile creations (which happens on new product download). [https://mozilla.cloud.looker.com/explore/accounts\_backend/events\_stream\_table?qid=FMbFE0WlX2MjS3WqhGWoaX\&origin\_space=374\&toggle=fil,vis](https://mozilla.cloud.looker.com/explore/accounts_backend/events_stream_table?qid=FMbFE0WlX2MjS3WqhGWoaX&origin_space=374&toggle=fil,vis)

Dip in glean events around the same time period [https://mozilla.cloud.looker.com/explore/accounts\_backend/events\_stream\_table?qid=FMbFE0WlX2MjS3WqhGWoaX\&origin\_space=374\&toggle=fil,vis](https://mozilla.cloud.looker.com/explore/accounts_backend/events_stream_table?qid=FMbFE0WlX2MjS3WqhGWoaX&origin_space=374&toggle=fil,vis)

Glean data would suggest that click events were affected about \~25% during the time period of the incident

[^1]:  This is a CDN, so some pages TTL was still good in some regions, so this percentage isn’t a completely even distribution. Further, 14% was at the peak of the issue, not for the entire 19mins.
