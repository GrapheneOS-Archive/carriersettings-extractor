package carrier_settings

import (
	"path"

	"android/soong/android"
	"android/soong/genrule"
)

func carrierSettingsGenRuleDefaults(ctx android.LoadHookContext) {
	type props struct {
		Srcs []string
	}

	p := &props{}
	p.Srcs = []string{path.Join("google_devices", ctx.Config().DeviceName(), "proprietary/product/etc/CarrierSettings/*.pb")}

	ctx.AppendProperties(p)
}

func init() {
	android.RegisterModuleType("carrier_settings_genrule_defaults", carrierSettingsGenRuleDefaultsFactory)
}

func carrierSettingsGenRuleDefaultsFactory() android.Module {
	module := genrule.DefaultsFactory()
	android.AddLoadHook(module, carrierSettingsGenRuleDefaults)

	return module
}
